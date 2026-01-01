import z from "zod";

// Individual point schema
export const MediapipeGPUPointSchema = z.object({
    name: z.string(),
    x: z.number(),
    y: z.number(),
    z: z.number(),
    visibility: z.number(),
});

// Metadata schema
export const MediapipeGPUMetadataSchema = z.object({
    n_body_detected: z.number(),
    image_width: z.number(),
    image_height: z.number(),
});

// Single camera observation schema
export const MediapipeGPUOverlaySchema = z.object({
    message_type: z.literal("mediapipe_gpu_overlay"),
    camera_id: z.string(),
    frame_number: z.number(),
    body_points: z.array(MediapipeGPUPointSchema),
    metadata: MediapipeGPUMetadataSchema,
});

// Multi-camera message schema (matches CharucoOverlayDataMessage structure)
export const MediapipeGPUOverlayDataMessageSchema = z.record(z.string(), MediapipeGPUOverlaySchema);

// Type exports
export type MediapipeGPUPoint = z.infer<typeof MediapipeGPUPointSchema>;
export type MediapipeGPUMetadata = z.infer<typeof MediapipeGPUMetadataSchema>;
export type MediapipeGPUObservation = z.infer<typeof MediapipeGPUOverlaySchema>;
export type MediapipeGPUOverlayDataMessage = z.infer<typeof MediapipeGPUOverlayDataMessageSchema>;
