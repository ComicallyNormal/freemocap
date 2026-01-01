from typing import Literal
from pydantic import BaseModel, Field
import logging 
from skellycam.core.types.type_overloads import CameraIdString
# from skellytracker.trackers.mediapipe_tracker.mediapipe_observation import MediapipeObservation
from skellytracker.trackers.mediapipe_gpu_tracker.mediapipe_gpu_observation import MediapipeGPUObservation


logger = logging.getLogger(__name__)

class MediapipeGPUPointModel(BaseModel):
    """A single detected Mediapipe landmark point."""
    name: str = Field(description="Landmark name")
    x: float = Field(description="X coordinate in image space")
    y: float = Field(description="Y coordinate in image space")
    z: float = Field(description="Z coordinate (normalized depth)")
    visibility: float = Field(description="Visibility confidence 0-1", ge=0, le=1)


class MediapipeGPUMetadataModel(BaseModel):
    """Metadata about the mediapipe detection."""
    n_body_detected: int = Field(description="Number of body landmarks detected")
    image_width: int = Field(description="Width of the image in pixels")
    image_height: int = Field(description="Height of the image in pixels")


class MediapipeGPUOverlayData(BaseModel):
    """Complete message for transmitting mediapipe observation over websocket."""
    message_type: Literal["mediapipe_gpu_overlay"] = "mediapipe_gpu_overlay"
    camera_id: CameraIdString = Field(description="ID of the camera that produced this observation")
    frame_number: int = Field(description="Frame number of this observation")
    body_points: list[MediapipeGPUPointModel] = Field(
        default_factory=list,
        description="List of detected body landmark points"
    )
    metadata: MediapipeGPUMetadataModel = Field(description="Detection metadata and statistics")

    @classmethod
    def from_mediapipe_observation(
            cls,
            *,
            camera_id: CameraIdString,
            observation: MediapipeGPUObservation,
            scale: float =.5,
            include_face: bool = True,
            face_type: str = "contour",  # "contour" or "tesselation"
    ):
        """
        Convert MediapipeObservation to Pydantic message model for websocket transmission.

        Args:
            camera_id: ID of the camera that produced this observation
            observation: The MediapipeObservation to serialize
            scale: Scale factor for coordinates (default 1.0)
            include_face: Whether to include face landmarks
            face_type: Type of face landmarks to include ("contour" or "tesselation")

        Returns:
            MediapipeOverlayData ready for JSON serialization
        """
        
        # Get all points with proper scaling
        all_points = observation.all_points(dimensions=3, face_type=face_type, scale_by=scale)
        
        # Build body points
        body_points: list[MediapipeGPUPointModel] = []
        # logger.info("length of landmark names: "+str(len(observation.body_landmark_names)))
        # logger.info("length of pos landmarks: "+str(len(observation.pose_landmarks.landmark)))

        if observation.pose_landmarks is not None and len(observation.pose_landmarks.landmark)>0:
            for name in observation.body_landmark_names:
                if name in all_points:
                    x, y, z = all_points[name]
                    # Get visibility from the original landmark
                    landmark_idx = observation.body_landmark_names.index(name)
                    visibility = observation.pose_landmarks.landmark[landmark_idx].visibility if observation.pose_landmarks else 0.0
                    
                    body_points.append(
                        MediapipeGPUPointModel(
                            name=name,
                            x=float(x),
                            y=float(y),
                            z=float(z),
                            visibility=float(visibility),
                        )
                    )

        
        # Build metadata
        metadata = MediapipeGPUMetadataModel(
            n_body_detected=len(body_points),
            image_width=observation.image_size[0],
            image_height=observation.image_size[1],
        )
        
        # Build complete message
        return cls(
            camera_id=camera_id,
            frame_number=observation.frame_number,
            body_points=body_points,
            metadata=metadata,
        )

