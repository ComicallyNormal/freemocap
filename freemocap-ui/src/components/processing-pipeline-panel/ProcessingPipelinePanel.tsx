import React, {useState,useMemo,useCallback} from "react";
import {Box, Typography, useTheme, Stack, TextField, FormControl, InputLabel, Select, MenuItem} from "@mui/material";
import {SimpleTreeView} from "@mui/x-tree-view/SimpleTreeView";
import {TreeItem} from "@mui/x-tree-view/TreeItem";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import LanIcon from '@mui/icons-material/Lan';
import PipelineConnectionStatus from "@/components/processing-pipeline-panel/PipelineConnectionStatus";
import {RecordingInfoPanel} from "@/components/recording-info-panel/RecordingInfoPanel";
import {useAppDispatch, useAppSelector} from "@/store/hooks";

import {
    pipelineConfigUpdated,
    updatePipelineModelOnServer,
    selectIsPipelineConnected,
    selectCanSetModelPipeline,
    selectPipelineConfig
} from "@/store/slices/pipeline";

    // const isConnected = useAppSelector(selectIsPipelineConnected);
    // const isLoading = useAppSelector(selectIsPipelineLoading);


export const ProcessingPipelinePanel: React.FC = () => {
    const theme = useTheme();
    const [expandedItems, setExpandedItems] = useState<string[]>([
        'pipeline-main',
        'calibration-intrinsic',
        'calibration-extrinsic',
        'mocap-task'
    ]);

        type ModelPreset = 'holistic' | 'gpu_accelerated' | 'custom';

        interface ModelPresetConfig {
            modelName: string;
        }

        const MODEL_PRESETS: Record<Exclude<ModelPreset, 'custom'>, ModelPresetConfig> = {
            'holistic': { modelName: "holistic"},
            'gpu_accelerated': { modelName: "gpu_accelerated"},
        };

    const handleExpandedItemsChange = (
        event: React.SyntheticEvent,
        itemIds: string[]
    ): void => {
        setExpandedItems(itemIds);
    };


    const cachedConfig = useAppSelector(selectPipelineConfig);
    const canUpdateModel = useAppSelector(selectCanSetModelPipeline);
    const isConnected = useAppSelector(selectIsPipelineConnected)
    console.log("is connected? "+ isConnected)

    // Determine current model preset based on config values //FIXME: HARDCODING DEFAULT
    const currentPreset = useMemo<ModelPreset>(() => {
        for (const [preset, presetConfig] of Object.entries(MODEL_PRESETS)) { 
                const globalPipelineConfig = cachedConfig
            
            if (
                presetConfig.modelName === globalPipelineConfig?.modelName
            ) {
                return preset as ModelPreset;
            }
        }
        return 'custom';
    }, []);

    const dispatch = useAppDispatch();

    const updateModelConfig = useCallback(
        (updates: Partial<ModelPresetConfig>) => {
            console.log("updateModelConfig Hit")
            // Update local state first
            dispatch(pipelineConfigUpdated(updates));
            // Then sync to server - this reads from the updated state
            dispatch(updatePipelineModelOnServer());
        },
        [dispatch]
    );

    const handlePresetChange = useCallback((preset: ModelPreset): void => {
        if (preset === 'custom') {
            console.log("doing nothing")
            // Don't change values when switching to custom
            return;
        }
        const presetConfig = MODEL_PRESETS[preset];
        updateModelConfig({
            modelName: preset
        });
    }, [updateModelConfig]);


    return (
        <Box
            sx={{
                color: "text.primary",
                backgroundColor: theme.palette.primary.main,
                borderRadius: 1,
                mb: 2,
            }}
        >
            <SimpleTreeView
                expandedItems={expandedItems}
                onExpandedItemsChange={handleExpandedItemsChange}
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon,
                }}
                sx={{ flexGrow: 1 }}
            >
                <TreeItem
                    itemId="pipeline-main"
                    label={
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                width: "100%",
                                py: 1,
                            }}
                        >
                            <LanIcon sx={{ transform: 'scaleY(-1.05) scaleX(1)' }} />

                            <Typography sx={{ pl: 1, flexGrow: 1 }} variant="h6" component="div">
                                Realtime Pipeline
                            </Typography>
                            <PipelineConnectionStatus />
                        </Box>
                    }
                >
                </TreeItem>
                <TreeItem
                    itemId="pipeline-main-2"
                    label={
                        <Box
                            sx={{
                                display: "flex",
                                alignItems: "center",
                                width: "100%",
                                py: 1,
                            }}
                        >
                            <LanIcon sx={{ transform: 'scaleY(-1.05) scaleX(1)' }} />

                            <Typography sx={{ pl: 1, flexGrow: 1 }} variant="h6" component="div">
                                Realtime AI Model
                            </Typography>
                                                {/* Dropdown list of AI models*/}
                                                <Stack direction="row" spacing={2}>
                                                    <FormControl size="small" sx={{ minWidth: 140 }}>
                                                        <InputLabel id="model-preset-label">Preset</InputLabel>
                                                        <Select
                                                            labelId="model-preset-label"
                                                            value={cachedConfig.modelName}
                                                            label="Preset"
                                                            onChange={(e) => handlePresetChange(e.target.value as ModelPreset)}
                                                            disabled={!isConnected}
                                                            sx={{color: theme.palette.text.primary}}
                                                        >
                                                            <MenuItem value="holistic">Holistic</MenuItem>
                                                            <MenuItem value="gpu_accelerated">GPU Accelerated</MenuItem>
                                                            <MenuItem value="custom">Custom</MenuItem>
                                                        </Select>
                                                    </FormControl>
                                                </Stack>
                        </Box>
                    }
                >
                </TreeItem>
            </SimpleTreeView>
        </Box>
    );
};
