import logging
import multiprocessing
import traceback
from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, ConfigDict
from skellycam.core.ipc.shared_memory.camera_group_shared_memory import CameraGroupSharedMemory, \
    CameraGroupSharedMemoryDTO
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString, TopicSubscriptionQueue
from skellycam.utilities.wait_functions import wait_1ms

from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.charuco_observation_aggregator import \
    get_last_successful_calibration_toml_path
from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.calibration_helpers.freemocap_anipose import \
    AniposeCameraGroup
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.mocap_helpers.triangulate_trajectory_array import \
    triangulate_frame_observations,is_data_valid
from freemocap.core.pipeline.realtime_pipeline.realtime_tasks.calibration_task.shared_view_accumulator import \
    SharedViewAccumulator
from freemocap.core.types.type_overloads import Point3d, PipelineIdString
from freemocap.pubsub.pubsub_topics import CameraNodeOutputMessage, PipelineConfigUpdateTopic, ProcessFrameNumberTopic, \
    ProcessFrameNumberMessage, AggregationNodeOutputMessage, AggregationNodeOutputTopic, CameraNodeOutputTopic, \
    PipelineConfigUpdateMessage, ShouldCalibrateTopic
from freemocap.core.pipeline.realtime_pipeline.websocket_broadcaster import WebSocketBroadcaster
from freemocap.core.pipeline.realtime_pipeline.steamvr_helper import transform_to_json, full_conversion, full_conversion_gpt
from ajc27_freemocap_blender_addon.core_functions.main_controller import MainController
from ajc27_freemocap_blender_addon.data_models.parameter_models.load_parameters_config import \
    load_default_parameters_config


import json
from ajc27_freemocap_blender_addon.core_functions.setup_scene.clear_scene import clear_scene


logger = logging.getLogger(__name__)


class RealtimeAggregationNodeState(BaseModel):
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
class RealtimeAggregationNode:
    shutdown_self_flag: multiprocessing.Value
    worker: multiprocessing.Process

    @classmethod
    def create(cls,
               config: RealtimePipelineConfig,
               camera_group_id: CameraGroupIdString,
               subprocess_registry: list[multiprocessing.Process],
               camera_group_shm_dto: CameraGroupSharedMemoryDTO,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"CameraGroup-{camera_group_id}-AggregationNode",
                                         kwargs=dict(config=config,
                                                     camera_group_id=camera_group_id,
                                                     ipc=ipc,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     camera_group_shm_dto=camera_group_shm_dto,
                                                     camera_node_subscription=ipc.pubsub.topics[
                                                         CameraNodeOutputTopic].get_subscription(),
                                                     pipeline_config_subscription=ipc.pubsub.topics[
                                                         PipelineConfigUpdateTopic].get_subscription(),
                                                     should_calibrate_subscription=ipc.pubsub.topics[
                                                         ShouldCalibrateTopic].get_subscription(),
                                                     ),

                                         )
        subprocess_registry.append(worker)
        return cls(shutdown_self_flag=shutdown_self_flag,
                   worker=worker
                   )

    @staticmethod
    def _run(config: RealtimePipelineConfig,
             camera_group_id: CameraGroupIdString,
             ipc: PipelineIPC,
             shutdown_self_flag: multiprocessing.Value,
             camera_group_shm_dto: CameraGroupSharedMemoryDTO,
             camera_node_subscription: TopicSubscriptionQueue,
             pipeline_config_subscription: TopicSubscriptionQueue,
             should_calibrate_subscription: TopicSubscriptionQueue
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        logger.debug("AggregationNode  - starting main loop")
        try:
            logger.debug(f"Starting aggregation process for camera group {camera_group_id}")
            camera_node_outputs: dict[CameraIdString, CameraNodeOutputMessage | None] = {camera_id: None for camera_id
                                                                                         in
                                                                                         config.camera_configs.keys()}
            camera_group_shm = CameraGroupSharedMemory.recreate(shm_dto=camera_group_shm_dto,
                                                                read_only=True)
            shared_view_accumulator = SharedViewAccumulator.create(camera_ids=config.camera_ids)
            latest_requested_frame: int = -1
            last_received_frame: int = -1
            anipose_camera_group = AniposeCameraGroup.load(str(get_last_successful_calibration_toml_path()))
            #fname = "sample_skeleton_points.txt"
            #save_directory = "/home/alexmini/Documents/Projects/freemocap_forks/Mediapipe-VR-Fullbody-Tracking/test_data"             
            #file_reader = open(save_directory + "/"+fname, "a", encoding="utf-8")
          # Initialize and start WebSocket broadcaster
            ws_broadcaster = WebSocketBroadcaster(host="0.0.0.0", port=8765)
            ws_broadcaster.start()
            logger.info("WebSocket broadcaster started on ws://0.0.0.0:8765")

            recording_path = "/home/alexmini/freemocap_data/realtime"
            blend_file_path = recording_path
            ground_plane_controller = MainController(recording_path=recording_path,
            blend_file_path=blend_file_path,
            config=load_default_parameters_config(),
            realtime=True)
            logger.info("Initialized dummy controller")
            controller_config = load_default_parameters_config()

            
            ground_plane_counter =0
            mega_payload = []
            mega_reproj_payload = []
            center = None
            x_forward = None
            y_left = None
            ground_plane_operation_successful = False

            while ipc.should_continue and not shutdown_self_flag.value:
                wait_1ms()
                
                # Check for updated Pipeline Config
                while not pipeline_config_subscription.empty():
                    pipeline_config_message: PipelineConfigUpdateMessage = pipeline_config_subscription.get()#NOTE THIS
                    config = pipeline_config_message.pipeline_config
                    logger.info(f"AggregationNode for camera group {camera_group_id} received updated config")

                # Check if we should request a new frame to process
                if camera_group_shm.latest_multiframe_number > latest_requested_frame and last_received_frame >= latest_requested_frame:
                    ipc.pubsub.topics[ProcessFrameNumberTopic].publish(
                        ProcessFrameNumberMessage(frame_number=camera_group_shm.latest_multiframe_number))
                    latest_requested_frame = camera_group_shm.latest_multiframe_number

                # Check for Camera Node Output
                if not camera_node_subscription.empty():
                    camera_node_output_message: CameraNodeOutputMessage = camera_node_subscription.get()
                    camera_id = camera_node_output_message.camera_id
                    if not camera_id in config.camera_configs.keys():
                        raise ValueError(
                            f"Camera ID {camera_id} not in camera IDs {list(config.camera_configs.keys())}")
                    camera_node_outputs[camera_id] = camera_node_output_message

                # Check if ready to process a frame output
                if all([isinstance(camera_node_output_message, CameraNodeOutputMessage) for camera_node_output_message
                        in
                        camera_node_outputs.values()]):
                    if not all([camera_node_output_message.frame_number == latest_requested_frame for
                                camera_node_output_message in camera_node_outputs.values()]):
                        logger.warning(
                            f"Frame numbers from tracker results do not match expected ({latest_requested_frame}) - got {[camera_node_output_message.frame_number for camera_node_output_message in camera_node_outputs.values()]}")
                    last_received_frame = latest_requested_frame

                    # shared_view_accumulator.receive_camera_node_output(
                    #     camera_node_output_by_camera=camera_node_outputs,
                    #     multi_frame_number=latest_requested_frame)

                    data_is_valid = is_data_valid(frame_number=latest_requested_frame,
                                                                    frame_observations_by_camera={camera_id: camera_node_outputs[camera_id].observation
                                                        for camera_id in camera_node_outputs.keys()},
                                                                    anipose_camera_group=anipose_camera_group,)
                    if(data_is_valid):

                        triangulated = triangulate_frame_observations(frame_number=latest_requested_frame,
                                                                    frame_observations_by_camera={camera_id: camera_node_outputs[camera_id].observation
                                                        for camera_id in camera_node_outputs.keys()},
                                                                    anipose_camera_group=anipose_camera_group,
                                                                    calculate_reprojection_error=True
                                                                    )

                        aggregation_output: AggregationNodeOutputMessage = AggregationNodeOutputMessage(
                            frame_number=latest_requested_frame,
                            pipeline_id=ipc.pipeline_id,
                            camera_group_id=camera_group_id,
                            pipeline_config=config,
                            camera_node_outputs=camera_node_outputs,
                            tracked_points3d=triangulated.to_point_dictionary()
                        )
                        ipc.pubsub.topics[AggregationNodeOutputTopic].publish(aggregation_output)
                        camera_node_outputs = {camera_id: None for camera_id in camera_node_outputs.keys()}
                        # logger.info("saving output to file")
                        # json_to_write = triangulated.to_json()
                        # file_reader.write(json_to_write)
                        # file_reader.write("\n")
                        point_list = triangulated.to_point_list()

                        reprojection_error = triangulated.reprojection_error
                        
                        # print("Reprojection error is not none right?")
                        # print(reprojection_error !=None)
                         
                        # logger.info(reprojection_error) #error of observation
                        # logger.info("calculated reprojection error shape: ",reprojection_error.shape)

                        if(len(point_list)==33 and type(reprojection_error) != None and config.mocap_task_config.modelName == "gpu_accelerated"):
                            pose_json =""
                            final_payload = ""
                            valid_pose = False
                            try:
                                #Note our race condition right now, we need this to start happening only if a client is open.    
                                if ground_plane_operation_successful:
                                    clear_scene()
                                    controller = MainController(recording_path=recording_path,
                                    blend_file_path=blend_file_path,
                                    config=controller_config,
                                    realtime=True) #it could be quicker to init per frame if it stops the memory leak.
                                    # logger.info("Initialized realtime_blender_addon")
                                    center_of_mass = np.empty(1)
                                    #wrapping reprojection error as list of one
                                    squeezed_error  = np.squeeze(reprojection_error)
                                    pose_mode =RealtimeAggregationNode.get_skeleton_mode() 
                                    if(pose_mode == "POINTS"):
                                        pose_json = controller.process_mediapipe_pose([point_list],[squeezed_error],center_of_mass,center,x_forward,y_left)
                                    elif(pose_mode== "JOINTS"):
                                        pose_json = controller.process_mediapipe_pose_as_gltf([point_list],[squeezed_error],center_of_mass,center,x_forward,y_left)
                                    elif(pose_mode =="RAW"):
                                        p_dict = {
                                            i:{"x":obj.x,"y":obj.y,"z":obj.z}
                                            for i,obj in enumerate(point_list)
                                        }
                                        pose_json= p_dict

                                    final_payload_dict = {"pose_mode":pose_mode, "pose": pose_json}
                                    final_payload = json.dumps(final_payload_dict, separators=(",", ":"))
                                    
                                    valid_pose = True
                                    print("valid pose!")


                            except Exception as e:
                                print(e)
                                traceback.print_exc()
                                pass
                                # print("invalid json,skipping")
                                # print(e)

                        # Broadcast to WebSocket clients
                            if ws_broadcaster.has_clients and valid_pose and ground_plane_operation_successful:
                                ws_broadcaster.broadcast_json(final_payload)
                                logger.debug(f"Broadcasted frame {latest_requested_frame} to {ws_broadcaster.client_count} WebSocket client(s)")

                        
                        # logger.info("output saved")
                            if ground_plane_counter<100:
                                mega_payload.append(point_list)
                                squeezed_error  = np.squeeze(reprojection_error) # [[]] -> []
                                mega_reproj_payload.append(squeezed_error)

                            elif ground_plane_counter == 100:
                                center_of_mass = np.empty(1) #Did we need this?
                                ground_plane_controller.load_freemocap_handler_from_data(mega_payload,mega_reproj_payload,center_of_mass) #Need pose data as ndarray, 
                                (c,x,y) = ground_plane_controller.get_ground_data_from_100_frames()
                                center = c
                                x_forward = x
                                y_left = y
                                ground_plane_operation_successful = True
                                logger.info("----Ground plane calibration complete!!!!")
                            ground_plane_counter+=1
                    else:
                        pass
                        logger.error("invalid data, skipping frame")


        except Exception as e:
            logger.error(f"Exception in AggregationNode for camera group {camera_group_id}: {e}", exc_info=True)
            ipc.kill_everything()
            raise
        finally:
            ws_broadcaster.stop()
            file_reader.close()
            logger.debug(f"Shutting down aggregation process for camera group {camera_group_id}")
    
    def start(self):
        logger.debug(f"Starting AggregationNode worker")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping AggregationNode worker")
        self.shutdown_self_flag.value = True
        self.worker.join()
        logger.debug(f"AggregationNode worker stopped")


    @staticmethod
    def get_skeleton_mode():
        standard_mode = "POINTS"
        alternate_mode = "JOINTS"
        raw_mode = "RAW"
        return raw_mode