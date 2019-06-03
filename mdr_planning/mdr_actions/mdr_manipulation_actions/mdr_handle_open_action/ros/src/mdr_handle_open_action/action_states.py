#!/usr/bin/python
import numpy as np

import rospy
import tf
import actionlib
from geometry_msgs.msg import PoseStamped

from pyftsm.ftsm import FTSMTransitions
from mas_execution.action_sm_base import ActionSMBase
from mdr_move_base_action.msg import MoveBaseAction, MoveBaseGoal
from mdr_move_forward_action.msg import MoveForwardAction, MoveForwardGoal
from mdr_move_arm_action.msg import MoveArmAction, MoveArmGoal
from mdr_handle_open_action.msg import HandleOpenGoal, HandleOpenResult

from importlib import import_module

class HandleOpenSM(ActionSMBase):
    # TODO: determine any other needed parameters
    def __init__(self, timeout=120.0,
                 gripper_controller_pkg_name='mdr_gripper_controller',
                 safe_arm_joint_config='folded',
                 move_arm_server='move_arm_server',
                 move_base_server='move_base_server',
                 move_forward_server='move_forward_server',
                 max_recovery_attempts=1):
        super(HandleOpenSM, self).__init__(
            'HandleOpen', [], max_recovery_attempts)
        self.timeout = timeout

        gripper_controller_module_name = '{0}.gripper_controller'.format(gripper_controller_pkg_name)
        GripperControllerClass = getattr(import_module(gripper_controller_module_name), 'GripperController')
        self.gripper = GripperControllerClass()

        self.safe_arm_joint_config = safe_arm_joint_config
        self.move_arm_server = move_arm_server
        self.move_base_server = move_base_server
        self.move_forward_server = move_forward_server

        self.retract_arm = False

    def init(self):
        try:
            self.move_arm_client = actionlib.SimpleActionClient(self.move_arm_server, MoveArmAction)
            rospy.loginfo('[handle_open] Waiting for %s server', self.move_arm_server)
            self.move_arm_client.wait_for_server()
        except Exception as exc:
            rospy.logerr('[handle_open] %s', str(exc))
            return FTSMTransitions.INIT_FAILED

        try:
            self.move_base_client = actionlib.SimpleActionClient(self.move_base_server, MoveBaseAction)
            rospy.loginfo('[pickup] Waiting for %s server', self.move_base_server)
            self.move_base_client.wait_for_server()
        except Exception as exc:
            rospy.logerr('[handle_open] %s', str(exc))
            return FTSMTransitions.INIT_FAILED

        try:
            self.move_forward_client = actionlib.SimpleActionClient(self.move_forward_server, MoveForwardAction)
            rospy.loginfo('[pickup] Waiting for %s server', self.move_forward_server)
            self.move_forward_client.wait_for_server()
        except Exception as exc:
            rospy.logerr('[handle_open] %s', str(exc))
            return FTSMTransitions.INIT_FAILED

        return FTSMTransitions.INITIALISED

    def running(self):
        pose = self.goal.handle_pose
        string handle_type = self.goal.handle_type
        init_end_effector_pose = self.goal.init_end_effector_pose
        pose.header.stamp = rospy.Time(0)
        pose_base_link = self.tf_listener.transformPose('base_link', pose)

        # TODO: determine whether this step is necessary for handle_open action:
        # if self.base_elbow_offset > 0:
        #     self.__align_base_with_pose(pose_base_link)

        #     # the base is now correctly aligned with the pose, so we set the
        #     # y position of the goal pose to the elbow offset
        #     pose_base_link.pose.position.y = self.base_elbow_offset

        rospy.loginfo('[handle_open] Opening the gripper...')
        self.gripper.open()

        rospy.loginfo('[handle_open] Preparing grasp end-effector pose')
        # TODO: implement __prepare_handle_grasp method
        # pose_base_link = self.__prepare_handle_grasp(pose_base_link)

        rospy.loginfo('[handle_open] Grasping...')
        arm_motion_success = self.__move_arm(
            MoveArmGoal.END_EFFECTOR_POSE, pose_base_link)
        if not arm_motion_success:
            rospy.logerr('[handle_open] Arm motion unsuccessful')
            self.result = self.set_result(False)
            return FTSMTransitions.DONE

        rospy.loginfo('[handle_open] Arm motion successful')

        rospy.loginfo('[handle_open] Closing the gripper')
        self.gripper.close()

        # Choice of either moving arm back, or moving robot base back:
        if self.retract_arm:
            rospy.loginfo('[handle_open] Moving the arm back')
            # TODO: define final_end_effector_pose, a geometry_msgs/PoseStamped goal message
            # self.__move_arm(MoveArmGoal.END_EFFECTOR_POSE, final_end_effector_pose)
        else:
            rospy.loginfo('[handle_open] Moving the base back')
            # TODO: define backward_movement_distance, a distance value (in m?)
            # self.__move_base_along_x(backward_movement_distance)

        # For now, assume success:
        self.result = self.set_result(True)
        return FTSMTransitions.DONE


    # TODO: implement a pre-grasp configuration that enables handle manipulation
    # The final end-affector position should match expected handle orientation
    def __prepare_handle_grasp(self, pose_base_link):
        rospy.loginfo('[PICKUP] Moving to a pregrasp configuration...')
        # ...
        return pose_base_link

    def __move_base_along_x(self, distance_to_move):
        movement_speed = np.sign(distance_to_move) * 0.1 # m/s
        movement_duration = distance_to_move / movement_speed
        move_forward_goal = MoveForwardGoal()
        move_forward_goal.movement_duration = movement_duration
        move_forward_goal.speed = movement_speed
        self.move_forward_client.send_goal(move_forward_goal)
        self.move_forward_client.wait_for_result()
        self.move_forward_client.get_result()

    def recovering(self):
        # TODO: if recovery behaviours are appropriate, fill this method with
        # the recovery logic
        rospy.sleep(5.)
        return FTSMTransitions.DONE_RECOVERING

    def set_result(self, success):
        result = HandleOpenResult()
        result.success = success
        return result