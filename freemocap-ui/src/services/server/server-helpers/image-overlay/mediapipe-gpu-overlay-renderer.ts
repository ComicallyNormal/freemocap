// mediapipe-overlay-renderer.ts

import {
    BaseOverlayRenderer,
    DrawStyle,
    Point2D
} from "@/services/server/server-helpers/image-overlay/image-overlay-system";

export interface MediapipeGPUPoint {
    name: string;
    x: number;
    y: number;
    z?: number;
    visibility?: number;
}

export interface MediapipeGPUObservation {
    message_type: 'mediapipe_gpu_overlay';
    camera_id: string;
    frame_number: number;
    body_points?: MediapipeGPUPoint[];
    metadata: {
        image_width: number;
        image_height: number;
        n_body_detected: number;
    };
}

export class MediapipeGPUOverlayRenderer extends BaseOverlayRenderer {
    // Aspect-specific styles
    private readonly bodyStyle: DrawStyle = {
        pointColor: '#00FF00',
        pointStroke: '#008800',
        pointRadius: 4,
        lineColor: '#00FF00',
        lineWidth: 2,
        labelColor: '#00FF00',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,  // Too many points to label
    };

    private readonly rightHandStyle: DrawStyle = {
        pointColor: '#FF6400',
        pointStroke: '#AA4400',
        pointRadius: 3,
        lineColor: '#FF6400',
        lineWidth: 1.5,
        labelColor: '#FF6400',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
    };

    private readonly leftHandStyle: DrawStyle = {
        pointColor: '#00AAFF',
        pointStroke: '#0066AA',
        pointRadius: 3,
        lineColor: '#00AAFF',
        lineWidth: 1.5,
        labelColor: '#00AAFF',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
    };

    private readonly faceStyle: DrawStyle = {
        pointColor: '#FFD700',
        pointStroke: '#AA9900',
        pointRadius: 1,
        lineColor: '#FFD700',
        lineWidth: 1,
        labelColor: '#FFD700',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 6,
        showLabels: false,
    };

    /**
     * Composite mediapipe overlay onto frame
     */
    public async compositeFrame(
        sourceBitmap: ImageBitmap,
        observation: MediapipeGPUObservation | null,
    ): Promise<ImageBitmap> {
        this.prepareCanvas(sourceBitmap);

        if (observation) {
            this.drawMediapipeOverlay(observation);
        }

        return this.createBitmap(sourceBitmap);
    }

    private drawMediapipeOverlay(observation: MediapipeGPUObservation): void {
        this.ctx.save();

        if (observation.body_points) {
            this.drawBodyAspect(observation.body_points);
        }
        // Draw info overlay
        this.drawMediapipeInfo(observation);

        this.ctx.restore();
    }

    private drawBodyAspect(points: MediapipeGPUPoint[]): void {
        if (points.length === 0) return;

        // Create point map for segment drawing
        const pointMap = new Map<string | number, Point2D>();
        const point2DArray: Point2D[] = [];

        for (const point of points) {
            const point2D: Point2D = {
                x: point.x,
                y: point.y,
                id: point.name,
                visibility: point.visibility,
            };
            pointMap.set(point.name, point2D);
            point2DArray.push(point2D);
        }

        // Draw segments first (behind points)
        if (this.modelInfo?.aspects['body']?.segment_connections) {
            this.drawSegments(pointMap, this.modelInfo.aspects['body'].segment_connections, {
                ...this.bodyStyle,
                lineColor: 'rgba(0, 255, 0, 0.6)',  // Semi-transparent
            });
        }

        // Draw points on top
        this.drawPoints(point2DArray, this.bodyStyle);

        // Highlight key points with labels
        this.drawKeyBodyPoints(pointMap);
    }

    private drawKeyBodyPoints(pointMap: Map<string | number, Point2D>): void {
        // Label only important landmarks for clarity
        const keyPoints = ['nose', 'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip'];

        for (const key of keyPoints) {
            const point = pointMap.get(key);
            if (point && this.isValidPoint(point)) {
                this.drawText(
                    key.replace('_', ' '),
                    point.x + 5,
                    point.y - 5,
                    8,
                    this.bodyStyle.labelColor,
                    this.bodyStyle.labelStroke,
                    1
                );
            }
        }
    }


    private drawMediapipeInfo(observation: MediapipeGPUObservation): void {
        const { metadata, frame_number } = observation;

        // Build detection status
        const detections: string[] = [];
        if (metadata.n_body_detected > 0) detections.push('Body');

        const statusText = detections.length > 0
            ? `✔ Detected: ${detections.join(', ')}`
            : '⚠ No detection';

        const statusColor = detections.length > 0 ? '#00FF00' : '#FF4444';

        // Draw info background
        this.ctx.fillStyle = this.INFO_BG;
        this.ctx.fillRect(5, 5, 500, 85);

        // Draw frame info
        this.drawText(
            `GPU Accelerated Mediapipe, Frame: ${frame_number}`,
            10,
            25,
            14,
            this.TEXT_COLOR,
            this.TEXT_STROKE,
            2
        );

        // Draw detection counts
        this.drawText(
            `Body: ${metadata.n_body_detected}`,
            10,
            50,
            14,
            this.TEXT_COLOR,
            this.TEXT_STROKE,
            2
        );

        // Draw status
        this.drawText(
            statusText,
            10,
            75,
            16,
            statusColor,
            this.TEXT_STROKE,
            2
        );
    }
}
