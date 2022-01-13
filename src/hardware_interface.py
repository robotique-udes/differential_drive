#!/usr/bin/env python

import rospy
from copy import deepcopy
from differential_drive.msg import VelocityTargets, Encoders
from std_msgs.msg import Float32, Float64, Int32
from sensor_msgs.msg import JointState

class MotorVelocityController:
    def __init__(self):
        self.upper_limit = 100
        self.lower_limit = -100
        self.rate = rospy.get_param("~rate", 50)
        self.maximum_speed = rospy.get_param("~max_speed", 0.5)  # m/s
        self.encoder_min = rospy.get_param("~encoder_min", -32768)
        self.encoder_max = rospy.get_param("~encoder_max", 32768)
        self.encoder_low_wrap = (self.encoder_max - self.encoder_min) * 0.3 + self.encoder_min
        self.encoder_high_wrap = (self.encoder_max - self.encoder_min) * 0.7 + self.encoder_min
        self.simulation = rospy.get_param("~simulation", False)

        self.raw_enc = [0.0] * 4  # Wheel encoders with limits
        self.prev_raw_enc = [0.0] * 4  # Previous wheel encoders with limits
        self.enc_multipliers = [0.0] * 4  # Number of times the encoders have wrapped around
        self.wrapped_enc = [0.0] * 4  # Wheel encoders with wrap around

        rospy.Subscriber("wheel_vel_target", VelocityTargets, self.velocityTargetsCB, queue_size=1)
        if self.simulation:
            rospy.Subscriber("/zeus/joint_states", JointState, self.jointStateCB)
        else:
            rospy.Subscriber("/ros_talon1/current_position", Float32, self.lfwheelCB)
            rospy.Subscriber("/ros_talon2/current_position", Float32, self.rfwheelCB)
            rospy.Subscriber("/ros_talon5/current_position", Float32, self.lbwheelCB)
            rospy.Subscriber("/ros_talon6/current_position", Float32, self.rbwheelCB)
        
        self.pub_wheel_enc = rospy.Publisher("wheel_enc", Encoders, queue_size=1)
        if self.simulation:
            self.pub_lf_cmd = rospy.Publisher("/zeus/left_front_wheel_velocity_controller/command", Float64, queue_size=1)
            self.pub_lm_cmd = rospy.Publisher("/zeus/left_middle_wheel_velocity_controller/command", Float64, queue_size=1)
            self.pub_lr_cmd = rospy.Publisher("/zeus/left_rear_wheel_velocity_controller/command", Float64, queue_size=1)
            self.pub_rf_cmd = rospy.Publisher("/zeus/right_front_wheel_velocity_controller/command", Float64, queue_size=1)
            self.pub_rm_cmd = rospy.Publisher("/zeus/right_middle_wheel_velocity_controller/command", Float64, queue_size=1)
            self.pub_rr_cmd = rospy.Publisher("/zeus/right_rear_wheel_velocity_controller/command", Float64, queue_size=1)
        else:
            self.pub_motor_cmd_left = rospy.Publisher("motor_cmd_left", Int32, queue_size=1)
            self.pub_motor_cmd_right = rospy.Publisher("motor_cmd_right", Int32, queue_size=1)

    def jointStateCB(self, msg):
        self.raw_enc = msg.position[0:6]
    def lfwheelCB(self, msg):
        self.raw_enc[0] = msg.data
        self.handleWrapAround(0)
    def lbwheelCB(self, msg):
        self.raw_enc[1] = msg.data
        self.handleWrapAround(1)
    def rfwheelCB(self, msg):
        self.raw_enc[2] = msg.data
        self.handleWrapAround(2)
    def rbwheelCB(self, msg):
        self.raw_enc[3] = msg.data
        self.handleWrapAround(3)

    def velocityTargetsCB(self, msg):
        left_cmd = self.limitValue(-msg.left_wheel_vel_target / self.maximum_speed * self.upper_limit)
        right_cmd = self.limitValue(msg.right_wheel_vel_target / self.maximum_speed * self.upper_limit)
        self.publishMotorCmds(left_cmd, right_cmd)
    
    def limitValue(self, value):
        if value > self.upper_limit:
            value = self.upper_limit
        elif value < self.lower_limit:
            value = self.lower_limit
        return value

    def handleWrapAround(self, i):
        if (self.raw_enc[i] < self.encoder_low_wrap and self.prev_raw_enc[i] > self.encoder_high_wrap):
            self.enc_multipliers[i] += 1
        elif (self.raw_enc[i] > self.encoder_high_wrap and self.prev_raw_enc[i] < self.encoder_low_wrap):
            self.enc_multipliers[i] -= 1
        # Calculate encoder values with wrap
        self.wrapped_enc[i] = self.raw_enc[i] + self.enc_multipliers[i] * (self.encoder_max - self.encoder_min)
        self.prev_raw_enc[i] = self.raw_enc[i]

    def publishMotorCmds(self, left, right):
        if self.simulation:
            left_cmd = Float64()
            right_cmd = Float64()
            left_cmd.data = left
            right_cmd.data = right
            self.pub_lf_cmd.publish(left_cmd)
            self.pub_lm_cmd.publish(left_cmd)
            self.pub_lr_cmd.publish(left_cmd)
            self.pub_rf_cmd.publish(right_cmd)
            self.pub_rm_cmd.publish(right_cmd)
            self.pub_rr_cmd.publish(right_cmd)
        else:
            left_cmd = Int32()
            right_cmd = Int32()
            left_cmd.data = left
            right_cmd.data = right
            self.pub_motor_cmd_left.publish(left_cmd)
            self.pub_motor_cmd_right.publish(right_cmd)

    def loop(self):
        rate = rospy.Rate(50)
        while not rospy.is_shutdown():
            wheel_enc = Encoders()
            wheel_enc.left_encoder = -(int((self.wrapped_enc[0] + self.wrapped_enc[1])/2))
            wheel_enc.right_encoder = (int((self.wrapped_enc[2] + self.wrapped_enc[3])/2))
            self.pub_wheel_enc.publish(wheel_enc)
        rate.sleep()
    

if __name__ == '__main__':
    try:
        rospy.init_node('motor_velocity_controller')
        rospy.loginfo("Starting the motor_velocity_controller node")
        motor_velocity_controller = MotorVelocityController()
        motor_velocity_controller.loop()
    except KeyboardInterrupt:
        # Stop motors
        MotorVelocityController.publishMotorCmds(0, 0)
        raise
    

