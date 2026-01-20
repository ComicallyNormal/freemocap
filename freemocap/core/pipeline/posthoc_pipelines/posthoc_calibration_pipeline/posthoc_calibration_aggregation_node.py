import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import TopicSubscriptionQueue, CameraIdString

from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseRecorder
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_pipeline import \
    CalibrationpipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.mocap_helpers.charuco_model_from_observations import \
    charuco_model_from_observations
from freemocap.core.pipeline.posthoc_pipelines.video_helper import VideoHelper, VideoMetadata
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.charuco_observation_aggregator import \
    anipose_calibration_from_charuco_observations, get_last_successful_calibration_toml_path

from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.shared_view_accumulator import CharucoObservations
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt, VideoIdString
from freemocap.pubsub.pubsub_topics import VideoNodeOutputMessage, VideoNodeOutputTopic
from freemocap.utilities.wait_functions import wait_1ms

import cv2
import numpy as np
from typing import List

logger = logging.getLogger(__name__)


class PosthocAgregationNodeState(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pipeline_id: PipelineIdString
    config: RealtimePipelineConfig
    alive: bool
    last_seen_frame_number: int | None = None
    calibration_task_state: object | None = None
    mocap_task_state: object = None  # TODO - this


@dataclass
class PosthocCalibrationAggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               calibration_pipeline_config: CalibrationpipelineConfig,
               video_metadata: dict[VideoIdString, VideoMetadata],
               pipeline_id: PipelineIdString,
               recording_info: RecordingInfo,
               subprocess_registry: list[multiprocessing.Process],
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"Pipeline-{pipeline_id}-PosthocAggregationNode",
                                         kwargs=dict(calibration_pipeline_config=calibration_pipeline_config,
                                                     pipeline_id=pipeline_id,
                                                     recording_info=recording_info,
                                                     video_metadata=video_metadata,
                                                     ipc=ipc,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     video_node_subscription=ipc.pubsub.topics[
                                                         VideoNodeOutputTopic].get_subscription(),
                                                     ),
                                         )
        subprocess_registry.append(worker)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=worker
                   )
    

    @staticmethod
    def aruco_marker_ids(board) -> List[int]:
        return list(board.getIds())
    @staticmethod
    def board_object_points(board) -> List[np.ndarray]:
        return list(board.getObjPoints())  # type: ignore
    @staticmethod
    def charuco_corner_ids(board_num_of_squares_x, board_num_of_squares_y) -> List[int]:
        return list(range((board_num_of_squares_x - 1) * (board_num_of_squares_y - 1)))

    @staticmethod
    def charuco_detect(detector,
                    board,
                    board_num_of_squares_x,
                    board_num_of_squares_y,
                    frame_number: int,
                    image: np.ndarray) -> CharucoObservation:
        if len(image.shape) == 2:
            grey_image = image
        else:
            grey_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


        (detected_charuco_corners,
            detected_charuco_ids,
            detected_aruco_corners,
            detected_aruco_ids) = detector.detectBoard(grey_image)

        # remove aruco markers not part of board definition
        if detected_aruco_ids is not None and len(detected_aruco_ids) > 0:
            valid_indices = [index for index, marker_id in enumerate(detected_aruco_ids.flatten()) if marker_id in PosthocCalibrationAggregationNode.aruco_marker_ids(board)]
            detected_aruco_corners = [detected_aruco_corners[i] for i in valid_indices]
            detected_aruco_ids = detected_aruco_ids[valid_indices].reshape(-1, 1)

        return CharucoObservation.from_detection_results(
            frame_number=frame_number,
            detected_charuco_corners=detected_charuco_corners,
            detected_charuco_corner_ids=detected_charuco_ids,
            detected_aruco_marker_corners=detected_aruco_corners,
            detected_aruco_marker_ids=detected_aruco_ids,
            image_size=(int(image.shape[0]), int(image.shape[1])),
            all_charuco_ids=PosthocCalibrationAggregationNode.charuco_corner_ids(board_num_of_squares_x,board_num_of_squares_y),
            all_aruco_ids=PosthocCalibrationAggregationNode.aruco_marker_ids(board),
            all_charuco_corners_in_object_coordinates=board.getChessboardCorners(),
            all_aruco_corners_in_object_coordinates=board.getObjPoints()
        )
# What the original does is basically act as a listener for the n number of cameras and aggregate their messages into 
# a dictionary that goes frame number - > device name -> message

#We should theoretically be able to construct a: list[ dict[CameraIdString, CharucoObservation]] where list idxs are frames
#some other way


    @staticmethod
    def jpegs_to_observations(charuco_detector,charuco_board,squares_x,squares_y,num_of_frames) ->tuple[list[dict[str,CharucoObservation]], dict[VideoIdString,VideoMetadata]] :
        observation_list :list[dict[str,CharucoObservation]] = []
        dummy_path = "/home/alexmini/Documents/Projects/freemocap_forks/calibration_hacks/calibration/"
        cam0_name = "1"
        cam1_name = "2"
        cam2_name = "3"
        cam0_int= 0
        cam1_int = 1
        cam2_int = 2
        metadata1 = None
        metadata2 = None
        metadata3 = None
        for i in range(0,num_of_frames,1):
            frame_num_str = str(i)
            vid0_path = f"{dummy_path}frame{frame_num_str}/cam{cam0_int}/cam{cam0_int}_frame_{frame_num_str}.jpeg"
            vid2_path = f"{dummy_path}frame{frame_num_str}/cam{cam1_int}/cam{cam1_int}_frame_{frame_num_str}.jpeg"
            vid4_path = f"{dummy_path}frame{frame_num_str}/cam{cam2_int}/cam{cam2_int}_frame_{frame_num_str}.jpeg"
            video_helper1 = VideoHelper.from_video_path(Path(vid0_path))
            video_helper2 = VideoHelper.from_video_path(Path(vid2_path))
            video_helper3 = VideoHelper.from_video_path(Path(vid4_path))
            ret1, frame_cam1  = video_helper1.video_reader.read()
            ret2, frame_cam2  = video_helper2.video_reader.read()
            ret3, frame_cam3  = video_helper3.video_reader.read() 
            frame_observations : dict[str,CharucoObservation]= dict()
            # char.detect()
            charuco_obs_cam1 = PosthocCalibrationAggregationNode.charuco_detect(charuco_detector,charuco_board,squares_x,squares_y,i,frame_cam1)
            charuco_obs_cam2 = PosthocCalibrationAggregationNode.charuco_detect(charuco_detector,charuco_board,squares_x,squares_y,i,frame_cam2)
            charuco_obs_cam3 = PosthocCalibrationAggregationNode.charuco_detect(charuco_detector,charuco_board,squares_x,squares_y,i,frame_cam3)


            frame_observations["0"] = charuco_obs_cam1
            frame_observations["1"] = charuco_obs_cam2
            frame_observations["2"] = charuco_obs_cam3

            if(i==0): #calculate metadata on first frame
                metadata1 = video_helper1.metadata
                metadata2 = video_helper2.metadata
                metadata3 = video_helper3.metadata
                
            observation_list.append(frame_observations)

        metadata_dict : dict[VideoIdString,VideoMetadata] = dict()
        metadata_dict["0"] = metadata1 #is it 0,2,4 or 0,1,2?
        metadata_dict["1"] = metadata2
        metadata_dict["2"] = metadata3

        return observation_list, metadata_dict
    
    
    @staticmethod
    def getCalibration(observations_by_frame: list[dict[str,CharucoObservation]],metadata_dict: dict[VideoIdString,VideoMetadata]):
        logger.info("entered getCalibration")
        # we could theoretically mock a calibration pipeline config
        
        dummy_path = "/home/alexmini/Documents/Projects/freemocap_forks/calibration_hacks/calibration_outputs/"
        record_info = PosthocCalibrationAggregationNode.to_recording_info(dummy_path)
        logger.info("recording path is: " + record_info.recording_directory + " full name is"+ record_info.full_recording_path)

        calibration_toml_path = anipose_calibration_from_charuco_observations(
        charuco_observations_by_frame=observations_by_frame,
        calibration_pipeline_config=CalibrationpipelineConfig(),
        recording_info=record_info, #TODO: Setting to none for now
        video_metadata=metadata_dict,
        use_charuco_as_groundplane=False,
        )   
        observation_recorders_by_video = {video_id: BaseRecorder() for video_id in
                                            observations_by_frame[0].keys()}
        for frame_number, charuco_observations_by_camera in enumerate(observations_by_frame):
            if not all(
                    [isinstance(output, CharucoObservation) for output in charuco_observations_by_camera.values()]):
                raise ValueError(
                    f"Non-CharucoObservation found in frame {frame_number} observations: {charuco_observations_by_camera}")
            for video_id, recorder in observation_recorders_by_video.items():
                recorder.add_observation(observation=charuco_observations_by_camera[video_id])

        charuco_board_model = charuco_model_from_observations(
            observation_recorders=observation_recorders_by_video,
            calibration_toml_path=get_last_successful_calibration_toml_path(),
            output_data_folder=Path(dummy_path),
        )

        logger.success(
            f"Posthoc calibration completed for pipeline DUMMY PIPELINE! Calibration file saved to {dummy_path}")


    @staticmethod
    def to_recording_info(recording_path : str) -> RecordingInfo:
        recordings_directory = Path(recording_path).parent
        recording_name = "RECORDING"
        # if not recording_name.endswith('_calibration'):
        #     recording_name += '_calibration'
        return RecordingInfo(
            recording_directory=str(Path(recordings_directory).parent).replace('~', str(Path.home())),
            recording_name=recording_name,
            mic_device_index=-1
        )



    @staticmethod
    def _run(calibration_pipeline_config: CalibrationpipelineConfig,
             recording_info: RecordingInfo,
             pipeline_id: PipelineIdString,
             video_metadata: dict[VideoIdString, VideoMetadata],
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             video_node_subscription: TopicSubscriptionQueue,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        start_frame = set(vm.start_frame for vm in video_metadata.values())
        end_frame = set(vm.end_frame for vm in video_metadata.values())
        if len(start_frame) != 1 or len(end_frame) != 1:
            raise ValueError(f"Mismatch in start/end frames across videos in pipeline {pipeline_id}: "
                             f"start_frames={start_frame}, end_frames={end_frame}")
        start_frame = start_frame.pop()
        end_frame = end_frame.pop()
        frame_numbers = set(range(start_frame, end_frame))
        video_ids = list(video_metadata.keys())

        logger.debug(f"PosthocCalibrationAggregationNode for pipeline id: '{pipeline_id}' starting main loop")
        try:

            video_outputs_by_frame: dict[FrameNumberInt, dict[VideoIdString, VideoNodeOutputMessage | None]] = {
                frame_number: {video_id: None for video_id in video_ids}
                for frame_number in frame_numbers
            }
            got_all_outputs_by_frame = {frame_number: False for frame_number in frame_numbers}

            if not len(video_outputs_by_frame) == len(frame_numbers):
                raise ValueError(f"Mismatch between video outputs by frame and recording info frame count - "
                                 f"{len(video_outputs_by_frame)} vs {len(frame_numbers)}")

            while not shutdown_self_flag.value and ipc.should_continue:
                wait_1ms()
                if not video_node_subscription.empty():
                    video_node_output_message: VideoNodeOutputMessage = video_node_subscription.get()

                    if not video_node_output_message.video_id in video_ids:
                        raise ValueError(
                            f"Video ID {video_node_output_message.video_id} not in recording info for pipeline {pipeline_id} - {recording_info.recording_name}")
                    video_outputs_by_frame[video_node_output_message.frame_number][
                        video_node_output_message.video_id] = video_node_output_message
                    if all([isinstance(value, VideoNodeOutputMessage) for value in
                           video_outputs_by_frame[video_node_output_message.frame_number].values()]):
                        # logger.info(f"Received all video node outputs for frame {video_node_output_message.frame_number} in pipeline {pipeline_id}")
                        got_all_outputs_by_frame[video_node_output_message.frame_number] = True

                if all(list(got_all_outputs_by_frame.values())):
                    break
            logger.info(f"All video node outputs received for pipeline {pipeline_id}, starting calibration")
            charuco_observations_by_frame: list[ dict[CameraIdString, CharucoObservation]] = []
            for frame_outputs in video_outputs_by_frame.values():
                if not all([isinstance(output, VideoNodeOutputMessage) for output in frame_outputs.values()]):
                    raise ValueError(
                        f"Missing video node outputs for frame in pipeline {pipeline_id}: {frame_outputs}")
                charuco_observations_by_frame.append({
                    video_id: output.observation
                    for video_id, output in frame_outputs.items()
                })



            squares_x = 5
            squares_y = 3
            square_length = 51   # meters (or any unit, just be consistent)
            marker_length = square_length *.8 # typically ~0.8 * square_length

            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

            charuco_board = cv2.aruco.CharucoBoard(
                (squares_x, squares_y),
                square_length,
                marker_length,
                aruco_dict
            )

            # ----------------------------
            # Create detector
            # ----------------------------

            charuco_params = cv2.aruco.CharucoParameters()
            detector_params = cv2.aruco.DetectorParameters()

            charuco_detector = cv2.aruco.CharucoDetector(
                charuco_board,
                charuco_params,
                detector_params
            )
            observations,metadata_dict = PosthocCalibrationAggregationNode.jpegs_to_observations(charuco_detector,charuco_board,squares_x,squares_y,5)
            PosthocCalibrationAggregationNode.getCalibration(observations,metadata_dict)



            calibration_toml_path = anipose_calibration_from_charuco_observations(
                charuco_observations_by_frame=charuco_observations_by_frame,
                calibration_pipeline_config=calibration_pipeline_config,
                recording_info=recording_info,
                video_metadata=video_metadata,
                # use_charuco_as_groundplane=True,
            )
            observation_recorders_by_video = {video_id: BaseRecorder() for video_id in
                                              charuco_observations_by_frame[0].keys()}
            for frame_number, charuco_observations_by_camera in enumerate(charuco_observations_by_frame):
                if not all(
                        [isinstance(output, CharucoObservation) for output in charuco_observations_by_camera.values()]):
                    raise ValueError(
                        f"Non-CharucoObservation found in frame {frame_number} observations: {charuco_observations_by_camera}")
                for video_id, recorder in observation_recorders_by_video.items():
                    recorder.add_observation(observation=charuco_observations_by_camera[video_id])

            charuco_board_model = charuco_model_from_observations(
                observation_recorders=observation_recorders_by_video,
                calibration_toml_path=get_last_successful_calibration_toml_path(),
                output_data_folder=Path(recording_info.full_recording_path) / "output_data",
            )

            logger.success(
                f"Posthoc calibration completed for pipeline {pipeline_id}! Calibration file saved to {recording_info.full_recording_path}")


        except Exception as e:
            logger.error(f"Exception in PosthocAggregationNode for recording: {recording_info.recording_name}: {e}", exc_info=True)
            ipc.kill_everything()
            raise
        finally:
            logger.debug(f"Shutting down aggregation process for  recording: {recording_info.recording_name}")

    def start(self):
        logger.debug(f"Starting PosthocAggregationNode worker")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping PosthocAggregationNode worker")
        self.shutdown_self_flag.value = True
        self.worker.join()




