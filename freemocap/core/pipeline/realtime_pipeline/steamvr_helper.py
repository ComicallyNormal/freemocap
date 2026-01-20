
from skellyforge.data_models.trajectory_3d import Point3d
import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import List
import json
import logging 

logger = logging.getLogger(__name__)

def mediapipeTo3dpose(lms : list[Point3d])->np.ndarray:
    #33 pose landmarks as in https://google.github.io/mediapipe/solutions/pose.html#pose-landmark-model-blazepose-ghum-3d
    #convert landmarks returned by mediapipe to skeleton that I use.
    #lms = results.pose_world_landmarks.landmark
    
    pose = np.zeros((29,3))

    pose[0]=[lms[28].x,lms[28].y,lms[28].z]
    pose[1]=[lms[26].x,lms[26].y,lms[26].z]
    pose[2]=[lms[24].x,lms[24].y,lms[24].z]
    pose[3]=[lms[23].x,lms[23].y,lms[23].z]
    pose[4]=[lms[25].x,lms[25].y,lms[25].z]
    pose[5]=[lms[27].x,lms[27].y,lms[27].z]

    pose[6]=[0,0,0]

    #some keypoints in mediapipe are missing, so we calculate them as avarage of two keypoints
    pose[7]=[lms[12].x/2+lms[11].x/2,lms[12].y/2+lms[11].y/2,lms[12].z/2+lms[11].z/2]
    pose[8]=[lms[10].x/2+lms[9].x/2,lms[10].y/2+lms[9].y/2,lms[10].z/2+lms[9].z/2]

    pose[9]=[lms[0].x,lms[0].y,lms[0].z]

    pose[10]=[lms[15].x,lms[15].y,lms[15].z]
    pose[11]=[lms[13].x,lms[13].y,lms[13].z]
    pose[12]=[lms[11].x,lms[11].y,lms[11].z]

    pose[13]=[lms[12].x,lms[12].y,lms[12].z]
    pose[14]=[lms[14].x,lms[14].y,lms[14].z]
    pose[15]=[lms[16].x,lms[16].y,lms[16].z]

    pose[16]=[pose[6][0]/2+pose[7][0]/2,pose[6][1]/2+pose[7][1]/2,pose[6][2]/2+pose[7][2]/2]

    #right foot
    pose[17] = [lms[31].x,lms[31].y,lms[31].z]  #forward
    pose[18] = [lms[29].x,lms[29].y,lms[29].z]  #back  
    pose[19] = [lms[25].x,lms[25].y,lms[25].z]  #up
    
    #left foot
    pose[20] = [lms[32].x,lms[32].y,lms[32].z]  #forward
    pose[21] = [lms[30].x,lms[30].y,lms[30].z]  #back
    pose[22] = [lms[26].x,lms[26].y,lms[26].z]  #up
    
    #right hand
    pose[23] = [lms[17].x,lms[17].y,lms[17].z]  #forward
    pose[24] = [lms[15].x,lms[15].y,lms[15].z]  #back
    pose[25] = [lms[19].x,lms[19].y,lms[19].z]  #up
    
    #left hand
    pose[26] = [lms[18].x,lms[18].y,lms[18].z]  #forward
    pose[27] = [lms[16].x,lms[16].y,lms[16].z]  #back
    pose[28] = [lms[20].x,lms[20].y,lms[20].z]  #up

    return pose


    
def get_basic_rot(pose3d : np.ndarray):

    ## guesses
    hip_left = 2
    hip_right = 3
    hip_up = 16
    
    knee_left = 1
    knee_right = 4
    
    ankle_left = 0
    ankle_right = 5

    #TODO
    #wrist_left
    #wrist_right
    
    # hip
    
    x = pose3d[hip_right] - pose3d[hip_left]
    w = pose3d[hip_up] - pose3d[hip_left]
    z = np.cross(x, w)
    y = np.cross(z, x)
    
    x = x/np.sqrt(sum(x**2))
    y = y/np.sqrt(sum(y**2))
    z = z/np.sqrt(sum(z**2))
    
    hip_rot = np.vstack((x, y, z)).T

    # right leg
    
    y = pose3d[knee_right] - pose3d[ankle_right]
    w = pose3d[hip_right] - pose3d[ankle_right]
    z = np.cross(w, y)
    if np.sqrt(sum(z**2)) < 1e-6:
        w = pose3d[hip_left] - pose3d[ankle_left]
        z = np.cross(w, y)
    x = np.cross(y,z)
    
    x = x/np.sqrt(sum(x**2))
    y = y/np.sqrt(sum(y**2))
    z = z/np.sqrt(sum(z**2))
    
    leg_r_rot = np.vstack((x, y, z)).T

    # left leg
    
    y = pose3d[knee_left] - pose3d[ankle_left]
    w = pose3d[hip_left] - pose3d[ankle_left]
    z = np.cross(w, y)
    if np.sqrt(sum(z**2)) < 1e-6:
        w = pose3d[hip_right] - pose3d[ankle_left]
        z = np.cross(w, y)
    x = np.cross(y,z)
    
    x = x/np.sqrt(sum(x**2))
    y = y/np.sqrt(sum(y**2))
    z = z/np.sqrt(sum(z**2))
    
    leg_l_rot = np.vstack((x, y, z)).T

    # left elbow
    y = pose3d[elbow_left] - pose3d[wrist_left]
    w = pose3d[shoulder_left] - pose3d[wrist_left]
    z = np.cross(w, y)
    if np.sqrt(sum(z**2)) < 1e-6:
        w = pose3d[hip_right] - pose3d[ankle_left]
        z = np.cross(w, y)
    x = np.cross(y,z)
    
    x = x/np.sqrt(sum(x**2))
    y = y/np.sqrt(sum(y**2))
    z = z/np.sqrt(sum(z**2))
    
    leg_l_rot = np.vstack((x, y, z)).T

    rot_hip = R.from_matrix(hip_rot).as_quat()
    rot_leg_r = R.from_matrix(leg_r_rot).as_quat()
    rot_leg_l = R.from_matrix(leg_l_rot).as_quat()


    #I'm on my own for elbows

    
    return rot_hip, rot_leg_l, rot_leg_r


import numpy as np
from scipy.spatial.transform import Rotation as R

def _safe_norm(v, eps=1e-8):
    n = np.linalg.norm(v)
    if n < eps:
        return None
    return v / n

def _snap_to_rotation(M):
    U, _, Vt = np.linalg.svd(M)
    M = U @ Vt
    if np.linalg.det(M) < 0:
        U[:, -1] *= -1
        M = U @ Vt
    return M

def _basis_from_xw(x_raw, w_raw, eps=1e-8):
    """
    Build basis from two edges:
      x = primary axis
      w = secondary (defines plane)
      z = x cross w
      y = z cross x
    Returns columns [x,y,z]
    """
    x = _safe_norm(x_raw, eps)
    if x is None:
        return None

    z = _safe_norm(np.cross(x, w_raw), eps)
    if z is None:
        return None

    y = _safe_norm(np.cross(z, x), eps)
    if y is None:
        return None

    return _snap_to_rotation(np.column_stack((x, y, z)))



def get_rot_packed29(pose29: np.ndarray):
    """
    pose29 is the output of mediapipeTo3dpose(): shape (29,3)

    Returns:
      hip_q, l_foot_q, r_foot_q, l_wrist_q, r_wrist_q
    where each quat is [x,y,z,w] (scipy).
    """

    # --- HIP ---
    HIP_L = 3   # your pose[3] = left hip (MP 23)
    HIP_R = 2   # your pose[2] = right hip (MP 24)
    HIP_UP = 16 # your synthetic "up" reference

    hip_left  = pose29[HIP_L]
    hip_right = pose29[HIP_R]
    hip_up    = pose29[HIP_UP]

    hip_M = _basis_from_xw(
        x_raw=hip_right - hip_left,
        w_raw=hip_up - hip_left
    )
    if hip_M is None:
        hip_M = np.eye(3)

    # --- FEET (your triads) ---
    # Right foot triad: forward/back/up
    RF_F, RF_B, RF_U = 17, 18, 19
    # Left foot triad
    LF_F, LF_B, LF_U = 20, 21, 22

    r_foot_M = _basis_from_xw(
        x_raw=pose29[RF_F] - pose29[RF_B],
        w_raw=pose29[RF_U] - pose29[RF_B],
    )
    if r_foot_M is None:
        r_foot_M = np.eye(3)

    l_foot_M = _basis_from_xw(
        x_raw=pose29[LF_F] - pose29[LF_B],
        w_raw=pose29[LF_U] - pose29[LF_B],
    )
    if l_foot_M is None:
        l_foot_M = np.eye(3)

    # --- WRISTS (your hand triads) ---
    # Right hand triad
    RH_F, RH_B, RH_U = 23, 24, 25  # back is wrist
    # Left hand triad
    LH_F, LH_B, LH_U = 26, 27, 28  # back is wrist

    r_wrist_M = _basis_from_xw(
        x_raw=pose29[RH_F] - pose29[RH_B],
        w_raw=pose29[RH_U] - pose29[RH_B],
    )
    if r_wrist_M is None:
        r_wrist_M = np.eye(3)

    l_wrist_M = _basis_from_xw(
        x_raw=pose29[LH_F] - pose29[LH_B],
        w_raw=pose29[LH_U] - pose29[LH_B],
    )
    if l_wrist_M is None:
        l_wrist_M = np.eye(3)

    hip_q     = R.from_matrix(hip_M).as_quat()
    l_foot_q  = R.from_matrix(l_foot_M).as_quat()
    r_foot_q  = R.from_matrix(r_foot_M).as_quat()
    l_wrist_q = R.from_matrix(l_wrist_M).as_quat()
    r_wrist_q = R.from_matrix(r_wrist_M).as_quat()

    return hip_q, l_foot_q, r_foot_q, l_wrist_q, r_wrist_q



def full_conversion(lms : List[Point3d]) ->list[dict]:
    # logger.info("length of lms: "+ str(len(lms)))
    transform_arr = []    
    hardcode_hmd_to_neck_offset = [0,-0.2,0.1]    #offset of your hmd to the base of your neck, to ensure the tracking is stable even if you look around. Default is 20cm down, 10cm back.
    hardcoded_headset_position = [0,0,0] # may need to query from steamvr
    hardcoded_headset_rotation = [0,0,0,1] #also query from steamvr


    headsetpos = [float(hardcoded_headset_position[0]),float(hardcoded_headset_position[1]),float(hardcoded_headset_position[2])]
    headsetrot = R.from_quat([float(hardcoded_headset_rotation[1]),float(hardcoded_headset_rotation[2]),float(hardcoded_headset_rotation[3]),float(hardcoded_headset_rotation[0])])#note the order has last as first, so is this x,y,z,w?
    neckoffset = headsetrot.apply(hardcode_hmd_to_neck_offset)   #the neck position seems to be the best point to allign to, as its well defined on
    
    converted_points = mediapipeTo3dpose(lms)
    rots = get_rot_packed29(converted_points)

    #dummy pose scale is replacement for params.posescale
    dummy_pose_scale = 1.0
                                                        #the skeleton (unlike the eyes/nose, which jump around) and can be calculated from hmd.
    converted_points = converted_points * dummy_pose_scale  #rescale skeleton to calibrated height
            #print(pose3d)
    offset = converted_points[7] - (headsetpos+neckoffset)    #calculate the position of the skeleton
    numadded = 3 #dormant, is a flag for where to start indices
    for i in [(0,1),(5,2),(6,0)]:
        joint = converted_points[i[0]] - offset       #for each foot and hips, offset it by skeleton position and send to steamvr
        # sendToSteamVR(f"updatepose {i[1]} {joint[0]} {joint[1]} {joint[2]} {rots[i[1]][3]} {rots[i[1]][0]} {rots[i[1]][1]} {rots[i[1]][2]} {params.camera_latency} 0.8")
        pos_dict = {"x":joint[0],"y":joint[1],"z":joint[2]}
        name_idx = rots[i[1]]
        quat_dict = {"w":name_idx[3],"x":name_idx[0],"y":name_idx[1],"z":name_idx[2]} #did we just flip the order?
        transform_dict = {}
        transform_dict["position"] = pos_dict
        transform_dict["rotation"] = quat_dict
        transform_arr.append(transform_dict)

    return transform_arr


LEFT_WRIST_IDX  = 15
RIGHT_WRIST_IDX = 16

def full_conversion_gpt(lms: list[Point3d]) -> list[dict]:
    transform_arr = []

    hardcode_hmd_to_neck_offset = [0, -0.2, 0.1]
    hardcoded_headset_position = [0, 0, 0]
    hardcoded_headset_rotation = [0, 0, 0, 1]  # w,x,y,z

    headsetpos = np.array(hardcoded_headset_position, dtype=float)
    headsetrot = R.from_quat([
        float(hardcoded_headset_rotation[1]),
        float(hardcoded_headset_rotation[2]),
        float(hardcoded_headset_rotation[3]),
        float(hardcoded_headset_rotation[0]),
    ])
    neckoffset = headsetrot.apply(hardcode_hmd_to_neck_offset)

    pose29 = mediapipeTo3dpose(lms)          # (29,3)
    hip_q, l_foot_q, r_foot_q, l_wrist_q, r_wrist_q = get_rot_packed29(pose29)

    dummy_pose_scale = 1.0
    pose29 = pose29 * dummy_pose_scale

    # You were anchoring using pose29[7] (shoulder midpoint). Keep for now:
    offset = pose29[7] - (headsetpos + neckoffset)

    # tracker_defs = (pose_index, quat)
    tracker_defs = [
        (3,  hip_q),        # hip position: pose[3] = left hip (you could also use midpoint of [2] and [3])
        (5,  l_foot_q),     # left ankle position
        (0,  r_foot_q),     # right ankle position
        (27, l_wrist_q),    # left wrist position (hand back)
        (24, r_wrist_q),    # right wrist position (hand back)
    ]

    for pose_idx, quat in tracker_defs:
        joint = pose29[pose_idx] - offset

        transform_arr.append({
            "position": {"x": float(joint[0]), "y": float(joint[1]), "z": float(joint[2])},
            "rotation": {"w": float(quat[3]), "x": float(quat[0]), "y": float(quat[1]), "z": float(quat[2])},
        })

    return transform_arr



def transform_to_json(tranform_arr : list) ->str:
    return json.dumps(tranform_arr, separators=(",", ":"))