import {CharucoObservation, CharucoOverlayDataMessage} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {MediapipeObservation, MediapipeOverlayDataMessage} from "@/services/server/server-helpers/image-overlay/mediapipe-types";
import {MediapipeGPUObservation, MediapipeGPUOverlayDataMessage} from "@/services/server/server-helpers/image-overlay/mediapipe-gpu-types";

// Union type for all observation data messages
export type ObservationDataMessage = CharucoOverlayDataMessage | MediapipeOverlayDataMessage | MediapipeGPUOverlayDataMessage;

// Union type for individual observations
export type Observation = CharucoObservation | MediapipeObservation | MediapipeGPUObservation;

// Type guard functions
export function isCharucoObservation(obs: Observation): obs is CharucoObservation {
    return obs.message_type === 'charuco_overlay';
}

export function isMediapipeObservation(obs: Observation): obs is MediapipeObservation {
    return obs.message_type === 'mediapipe_overlay';
}
export function isMediapipeGPUObservation(obs: Observation): obs is MediapipeGPUObservation {
    return obs.message_type === 'mediapipe_gpu_overlay';
}
