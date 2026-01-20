import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path
import cv2

from skellycam.core.types.type_overloads import WorkerType
# from skellytracker.trackers.mediapipe_tracker.mediapipe_detector import MediapipeDetector
from skellytracker.trackers.mediapipe_gpu_tracker.mediapipe_gpu_detector import MediapipeGPUDetector

from skellytracker.trackers.mediapipe_tracker.mediapipe_detector import MediapipeDetector

from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.posthoc_mocap_pipeline import \
    MocapPipelineTaskConfig

from freemocap.core.types.type_overloads import VideoIdString
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage

logger = logging.getLogger(__name__)


@dataclass
class MocapVideoNode:
    video_id: VideoIdString
    video_path: Path
    mocap_task_config: MocapPipelineTaskConfig
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               video_id: VideoIdString,
               video_path: Path,
               subprocess_registry: list[multiprocessing.Process],
               mocap_task_config: MocapPipelineTaskConfig,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"VideoProcessingNode-{video_path.stem}",
                                         kwargs=dict(
                                             video_id=video_id,
                                             video_path=video_path,
                                             ipc=ipc,
                                             mocap_task_config=mocap_task_config,
                                             shutdown_self_flag=shutdown_self_flag,
                                         ),
                                         )
        subprocess_registry.append(worker)
        return cls(video_id=video_id,
                   video_path=video_path,
                   shutdown_self_flag=shutdown_self_flag,
                   mocap_task_config=mocap_task_config,
                   worker=worker
                   )

    @staticmethod
    def _run(video_id: VideoIdString,
             video_path: Path,
             ipc: PipelineIPC,
             mocap_task_config: MocapPipelineTaskConfig,
             shutdown_self_flag: multiprocessing.Value,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)


        logger.info("video path for capture is: "+ str(video_path))
        video_reader = None
        if str(video_path).endswith("mp4"):
            logger.info("video file")
            video_reader = cv2.VideoCapture(str(video_path))
        else:
            logger.info("video capture")
            device = str(video_path)
            logger.info(f"trying to go to path: {video_path}")
            pipeline = (
            f"v4l2src device={device} ! "
            "image/jpeg,width={w},height={h},framerate={fps}/1 ! "
            "jpegdec ! videoconvert ! appsink drop=true sync=false"
            )        
            
            video_reader = cv2.VideoCapture(pipeline,cv2.CAP_GSTREAMER)

            # video_reader = cv2.VideoCapture(str(video_path),cv2.CAP_V4L2)


     

        success, image = video_reader.read()
        frame_number = 0
        logger.info(f"Starting video processing node for video: {video_path.stem}")
        if(mocap_task_config.modelName == "gpu_accelerated"):
            mediapipe_detector = MediapipeGPUDetector.create(config=mocap_task_config.detector_config)
        else:
            mediapipe_detector = MediapipeDetector.create()
        try:
            while success and not shutdown_self_flag.value and ipc.should_continue:
                mediapipe_observation = mediapipe_detector.detect(
                    frame_number=frame_number,
                    image=image)

                ipc.pubsub.publish(
                    topic_type=VideoNodeOutputTopic,
                    message=VideoNodeOutputMessage(
                        video_id=video_id,
                        frame_number=frame_number,
                        observation=mediapipe_observation,
                    ),
                )
                success, image = video_reader.read()
                frame_number+=1

        except Exception as e:
            logger.exception(f"Exception in video node for video: {video_path.stem} - {e}")
            ipc.kill_everything()
            raise e
        finally:
            logger.debug(f"Shutting down video processing node for video: {video_path.stem}")
            video_reader.release()
    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} for video: {self.video_path.stem}")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping {self.__class__.__name__} for video: {self.video_path.stem}")
        self.shutdown_self_flag.value = True
        self.worker.join()
