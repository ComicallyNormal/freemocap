import {createSlice,PayloadAction} from "@reduxjs/toolkit";
import {PipelineState,PipelineModelConfig} from "@/store/slices/pipeline/pipeline-types";
import {closePipeline, connectRealtimePipeline, updatePipelineModelOnServer} from "@/store/slices/pipeline/pipeline-thunks";
import {RootState} from '../../types';


const initialState: PipelineState = {
    cameraGroupId: null,
    pipelineId: null,
    isConnected: false,
    isLoading: false,
    error: null,
    config: {modelName:"gpu_accelerated"}
}

export const pipelineSlice = createSlice({
    name: 'pipeline',
    initialState,
    reducers: {
        // Manual state reset
        pipelineStateReset: (state) => {
            state.cameraGroupId = null;
            state.pipelineId = null;
            state.isConnected = false;
            state.isLoading = false;
            state.error = null;
        },
        pipelineConfigUpdated: (state : PipelineState, action: PayloadAction<Partial<PipelineModelConfig>>) => {
            state.config = { ...state.config, ...action.payload };
        },
    },
    extraReducers: (builder) => {
        builder
        // Connect Pipeline
            .addCase(connectRealtimePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(connectRealtimePipeline.fulfilled, (state, action) => {
                state.cameraGroupId = action.payload.camera_group_id;
                state.pipelineId = action.payload.pipeline_id;
                state.isConnected = true;
                state.isLoading = false;
            })
            .addCase(connectRealtimePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to connect pipeline';
            })

        // disconnect pipeline
         .addCase(closePipeline.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
            .addCase(closePipeline.fulfilled, (state) => {
                state.cameraGroupId = null;
                state.pipelineId = null;
                state.isConnected = false;
                state.isLoading = false;
            })
            .addCase(closePipeline.rejected, (state, action) => {
                state.isLoading = false;
                state.error = action.error.message || 'Failed to disconnect pipeline';
            })
                    // Update ML model pipeline
         .addCase(updatePipelineModelOnServer.pending, (state) => {
                state.isLoading = true;
                state.error = null;
            })
        .addCase(updatePipelineModelOnServer.fulfilled, (state) => {
            console.log("fulfilled")
            console.log(state)
            state.isLoading = false;
        })
        .addCase(updatePipelineModelOnServer.rejected, (state, action) => {
            state.isLoading = false;
            state.error = action.error.message || 'Failed to update pipeline model';
        });
    },
});

//selectors
export const selectPipelineConfig = (state: RootState) => state.pipeline.config;


export const {pipelineStateReset,pipelineConfigUpdated} = pipelineSlice.actions;
