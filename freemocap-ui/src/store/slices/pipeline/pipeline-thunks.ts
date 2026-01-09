import {createAsyncThunk} from "@reduxjs/toolkit";
import {RootState, selectSelectedCameraConfigs} from "@/store";
import {serverUrls} from "@/services";
import {PipelineConnectRequest, PipelineConnectResponse,} from "@/store/slices/pipeline/pipeline-types";

export const connectRealtimePipeline = createAsyncThunk<
    PipelineConnectResponse,
    PipelineConnectRequest | undefined,
    { state: RootState }>(
    'pipeline/connect',
    async (request={}, {getState}) => {
        const state = getState();

        const cameraConfigs = selectSelectedCameraConfigs(state);
        const response = await fetch(serverUrls.endpoints.pipelineConnectOrUpdate, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ camera_configs: cameraConfigs, ...request }),
        });

        if (!response.ok) {
            const error = await response.json()
            throw new Error(`Failed to connect pipeline: ${error.message || response.statusText}`);
        }
        return await response.json() as Promise<PipelineConnectResponse>;
    })


export const closePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'pipeline/close',
    async () => {
        const response = await fetch(serverUrls.endpoints.pipelineClose, {
            method: 'DELETE',
        });

        if (!response.ok) {
            console.error(`Failed to close pipeline: ${response.statusText}`);
        }
    }
);



// Helper function to extract detailed error info from failed responses
async function getDetailedErrorMessage(response: Response): Promise<string> {
    let errorDetails: unknown;

    try {
        // Try to parse JSON error response
        errorDetails = await response.json();
        console.error('❌ Server returned validation/error details:', errorDetails);
    } catch {
        // If not JSON, try to get text
        try {
            errorDetails = await response.text();
            console.error('❌ Server returned error text:', errorDetails);
        } catch {
            console.error('❌ Could not read error response body');
        }
    }

    // Build comprehensive error message
    const baseError = `HTTP ${response.status}: ${response.statusText}`;

    if (errorDetails) {
        // Pretty print the error details
        const detailsStr = typeof errorDetails === 'string'
            ? errorDetails
            : JSON.stringify(errorDetails, null, 2);
        return `${baseError}\n\nValidation/Error Details:\n${detailsStr}`;
    }

    return baseError;
}


export const updatePipelineModelOnServer = createAsyncThunk<
    { success: boolean; message?: string },
    void,
    { state: RootState; rejectValue: string }
>(
    'pipeline/updatemodel',
    async (_, { getState, rejectWithValue }) => {
        try {
            const state = getState();
            const config = state.pipeline.config
            const pipeState = state.pipeline
            const cameraConfigs = selectSelectedCameraConfigs(state);

            console.log('⚙️ Updating model config on server:', pipeState);
            console.log("updated model name will be: "+ config?.modelName)
            const fullJson = {"model_conf":config,"pipeline_config":{"camera_configs":cameraConfigs,"mocap_task_config":config}}
            console.log(fullJson)
            const response = await fetch(serverUrls.endpoints.pipelineUpdateModel, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fullJson),
            });

            if (!response.ok) {
                const errorMessage = await getDetailedErrorMessage(response);
                console.error("Error in model update request!")
                console.error(errorMessage)

                return rejectWithValue(errorMessage);
            }

            const result = await response.json();
            console.log('✅ Model updated on server:', result);
            return result;
        } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            console.error('❌ Failed to update model on server:', errorMessage);
            return rejectWithValue(errorMessage);
        }
    }
);




export const pauseUnpausePipeline = createAsyncThunk<void, void, { state: RootState }>(
    'cameras/pause',
    async () => {
        const response = await fetch(serverUrls.endpoints.pipelinePauseUnpause, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`Failed to pause/unpause cameras: ${response.statusText}`);
        }
    }
);
