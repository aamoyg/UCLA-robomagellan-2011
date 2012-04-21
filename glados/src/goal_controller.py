#!/usr/bin/python
# written by asa
# simple pid controller to get to a setpoint of some kind.
import time
import sys
import math
import yaml
from gps import *
import roslib; roslib.load_manifest('geometry_msgs')
roslib.load_manifest('nav_msgs')
roslib.load_manifest('gps_common')
from gps_common.msg import *
import rospy
from  geometry_msgs.msg import *
from nav_msgs.msg import *
from glados.srv import *
roslib.load_manifest('glados_sensors')
from glados_sensors.msg import *

waypoints_list = yaml.load(file('../../waypoints.yaml','r'))


def LLtoUTMConverter(lat,lon):
    rospy.wait_for_service('LLtoUTM')
    try:
        lltoutm = rospy.ServiceProxy('LLtoUTM', LLtoUTM)
        #print lltoutm.__dict__.keys()
        #print lltoutm.request_class.__dict__.keys()
        #request = lltoutm.request_class()
        #response = lltoutm.response_class()
        response = lltoutm(lat,lon)
        return response
        
    except rospy.ServiceException, e:
        print "Service call failed: %s"%e
        

class pid(object):
    def __init__(self):
        self.last_value = 0.
        self.err_x = 0.
        self.err_y = 0.
        self.Kp = 1
        self.Kd = .1
        self.Ki = .1
        self.output = {
            'linear':{
                'x':0.,
                'y':0.,
                'z':0.
                },
            'angular':{
                'x':0.,
                'y':0.,
                'z':0.
                }
            }
        self.target_angle = 0.
        
    def calc(self, current_pos, goal_pos):
        if current_pos['getData'] == False:
            return
        '''
        #testing
        #x
        self.err_x = goal_pos['x'] - current_pos['x']
        x_v = self.err_x*self.Kp
        if x_v != 0 and math.fabs(self.err_x) < 0.5*current_pos['x']:
            x_v = self.err_x*(self.Kp+self.Ki)
        #y
        self.err_y = goal_pos['y'] - current_pos['y']
        y_v = self.err_y*self.Kp
        if y_v != 0 and math.fabs(self.err_y) < 0.5*current_pos['y']:
            y_v = self.err_y*(self.Kp+self.Ki)

        v = float(math.sqrt((x_v*x_v + y_v*y_v)))
        
        if self.err_y < 0.:
            self.output['linear']['x'] = -v
        else:
            self.output['linear']['x'] = v
        if v != 0.:
            other_v = self.err_y/v #y2-y1/v
            angular_offset = math.fabs(other_v)
            if self.err_x < 0.:
                self.output['angular']['z'] = angular_offset
            else:
                self.output['angular']['z'] = -angular_offset
                
        else:
            self.output['angular']['z'] = 0.
        '''
        #difference calculation
        
        err_x = goal_pos['x'] - current_pos['x']
        self.err_x = err_x <= math.fabs(0.01) ? 0 : err_x
        err_y = goal_pos['y'] - current_pos['y']
        self.err_y = err_y <= math.fabs(0.01) ? 0 : err_x
        distance = float(math.sqrt(self.err_x*self.err_x+self.err_y*self.err_y))
        self.target_angle = (90 - (math.atan2(self.err_y,self.err_x)*(180/math.pi))) - (current_pos['heading']*(180/math.pi))
        print self.target_angle
        
        self.output['angular']['z'] = (self.target_angle*(math.pi)/(180))*self.Kp
        print self.output['angular']['z']
        
        if distance != 0.:
            self.output['linear']['x'] = 1.5
            
# http://cse.unl.edu/~carrick/courses/2011/496/lab2/lab2.html
class goalControl():
    def __init__(self):
        rospy.init_node('pid')
        #test value        
        self.goal_pos = waypoints_list
        self.current_goal_pos = {
            "hasCone":False,
            "x":0.,
            "y":0.
            }
        self.vel_pub = rospy.Publisher('cmd_vel', Twist)
        self.odom_sub = rospy.Subscriber('odom', Odometry, self.odom_handler)
        #TODO:sub to gpsd and compass to get current pos and heading
        #self.gps_sub = rospy.Subscriber('gps/fix', GPSFix, gps_handler)
        #self.imu_sub = rospy.Subscriber('imu', imu, imu_handler)
        self.pid = pid()
        self.rate = 1.0
        self.go = True
        
        self.current_pos = {
            'getData':True,
            'x':0.,
            'y':0.,
            'heading':0,
            'linear':{
                'x':0.,
                'y':0.,
                'z':0.
                },
            'angular':{
                'x':0.,
                'y':0.,
                'z':0.
                },
            'left_v':0.,
            'right_v':0.
            }
    def odom_handler(self, data):
        print data
        
    def gps_handler(self, data):
        pass
    
    def imu_handler(self, data):
        pass
    
    def goNextWaypoint(self):
        if not self.goal_pos:
            popout = self.goal_pos.pop(0)
            llutmresponse = LLtoUTMConverter(popout['latitude'], popout['longitude'])
            self.current_goal_pos['x'] = llutmresponse['easting']
            self.cuurent_goal_pos['y'] = llutmresponse['northing']
            self.go = True
        else:
            self.go = False
            
    def run(self):
        #print glados_sensors.__dict__.keys()
        self.goNextWaypoint()
        while (not rospy.is_shutdown()):#and (self.current_pos['getData']) and self.go :
            if (math.fabs(self.current_pos['x'] - self.current_goal_pos['x']) <= 0.01) and (math.fabs(self.current_pos['y'] - self.current_goal_pos['y']) <= 0.01):
                self.goNextWaypoint()
                
            self.pid.calc(self.current_pos, self.current_goal_pos)
            #increment current pos
            #self.current_pos['heading'] += (self.pid.output['angular']['z'])*self.pid.Kp

            #record twist msg
            self.current_pos['linear']['x'] = self.pid.output['linear']['x']
            self.current_pos['angular']['z'] = self.pid.output['angular']['z']
            
            #debug output
            '''
            print "goal pos:"
            print self.goal_pos[0]
            print "current pos:"
            print self.current_pos
            print "current twist:"
            print self.current_twist
            '''
            
            #publish twist msg
            twistOutput = Twist()
            twistOutput.linear.x = self.current_pos['linear']['x']
            twistOutput.linear.y = 0.
            twistOutput.linear.z = 0.
            twistOutput.angular.x = 0.
            twistOutput.angular.y = 0.
            twistOutput.angular.z = -self.current_pos['angular']['z']
            
            #emergency kill
            #twistOutput.linear.x = 0.
            #twistOutput.angular.z = 0.
            
            self.publish(twistOutput)
            rospy.sleep(self.rate)
            
        #stop the robot once it's runing out
        twistOutput = Twist()
        twistOutput.linear.x = 0.
        twistOutput.linear.y = 0.
        twistOutput.linear.z = 0.
        twistOutput.angular.x = 0.
        twistOutput.angular.y = 0.
        twistOutput.angular.z = 0.
        self.publish(twistOutput)
                
    def publish(self,output):
        self.vel_pub.publish(output)

if __name__ == '__main__':
    '''latitude = waypoints_list[0]['latitude']
    longitude = waypoints_list[0]['longitude']
    response = LLtoUTMConverter(latitude, longitude)
    print response'''
    g = goalControl()
    try:
        g.run()
    except rospy.ROSInterruptException: pass
	

