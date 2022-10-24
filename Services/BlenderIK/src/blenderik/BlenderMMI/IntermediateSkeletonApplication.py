# std-Library
from typing import List, Optional, Union
import logging

from macpath import join
logger = logging.getLogger(__name__)

# MOSIM This only belongs in the Adapter! Refactor
import MMIStandard.avatar.ttypes as tavatar

#Blender
import bpy
from mathutils import Matrix, Quaternion, Vector, Euler

def MVector2Vector(v) -> Vector:
    return Vector((-v.X, v.Y, v.Z))

def MQuaternion2Quaternion(q) -> Quaternion:
    return Quaternion((-q.W, -q.X, q.Y, q.Z))

VIRTUAL_JOINTS = ["LeftShoulder", "RightShoulder", "LeftHip", "RightHip"]

class IntermediateSkeletonApplication():
    """
    This class provides a set of helper functions to scale the intermediate 
    skeleton, to apply posture values from thrift and to read posture values 
    that can be directly sent to the MMIFramework over thrift. 
    """
    
    # Attributes:
    #
    # object
    # posture
    # base_matrix
    # zero_matrix
    # lowerlegLength   # naming!
    # thighLength
    
    bendThreshold = 0.5
    # effectorMap = { # Mosim-Name: (blenderbonename, Offset-Correction)
        # 'RightHand':('RightWrist', Quaternion((0.5,0.5,0.5,0.5))), 
        # 'LeftHand': ('LeftWrist', Quaternion((0.5,0.5,-0.5,-0.5))),
        # 'RightFoot': ('RightAnkle', Quaternion()),
        # 'LeftFoot': ('LeftFoot', Quaternion()),
        # 'RightWrist':('RightWrist', Quaternion((0.5,0.5,0.5,0.5))), 
        # 'LeftWrist': ('LeftWrist', Quaternion((0.5,0.5,-0.5,-0.5))),
        # 'RightFoot': ('RightAnkle', Quaternion()),
        # 'LeftFoot': ('LeftFoot', Quaternion()),
        # }
        
    effectorMap = { # Mosim-Name: (blenderbonename, Offset-Correction)
        # 'RightHand':('RightWrist', "RightElbow", Quaternion()), 
        # 'LeftHand': ('LeftWrist', "LeftElbow", Quaternion()),
        'RightAnkle': ('RightAnkle', "RightAnkle", Quaternion()),
        'LeftAnkle': ('LeftAnkle',"LeftAnkle", Quaternion()),
        'RightWrist':('RightWrist',"RightWrist", Quaternion()), 
        'LeftWrist': ('LeftWrist',"LeftWrist", Quaternion()),
        'T1T2Joint' : ("T1T2Joint", "T1T2Joint", Quaternion())
        # 'RightWrist':('RightWrist',"RightElbow", Quaternion()), 
        # 'LeftWrist': ('LeftWrist',"LeftElbow", Quaternion()),
        # 'RightFoot': ('RightAnkle',"RightKnee", Quaternion()),
        # 'LeftFoot': ('LeftAnkle',"LeftKnee", Quaternion()),
        }
    
    def __init__(self, avatar_id, posture: Optional[tavatar.MAvatarPosture] = None):
        """
        parameters:
            - avatar_id: "lalala"
            - posture: the tavatar.MAvatarPosture for scaling (if already existing)
        """
        self._object_id  = avatar_id
        self.posture = posture
        
        logger.info(f"New sceleton: {avatar_id}")
        
        self.ikConstraints = {bone.name: bone.constraints.get('IK') 
            for bone in self.object.pose.bones if bone.constraints.get('IK')
        }
        logger.debug(f"Found {len(self.ikConstraints)} ik-constraints: [{self.ikConstraints.keys()}]")
        [logger.debug("   c: %s: %s"%(bone, self.ikConstraints[bone])) for bone in self.ikConstraints]
        
        self.copyConstraints = {bone.name: bone.constraints.get('Copy Rotation') 
            for bone in self.object.pose.bones if bone.constraints.get('Copy Rotation')
        }
        logger.debug(f"Found {len(self.copyConstraints)} copy-constraints: [{self.copyConstraints.keys()}]")
        
        
        self.base_matrix = {}
        self.zero_matrix = {}
        
        self.disableAllConstraints()
        if posture is not None:
            self.ScaleMAvatarPosture(posture)
            
        if self.object is not None:
            RightKnee               = self.object.pose.bones['RightKnee']
            RightHip                = self.object.pose.bones['RightHip']
            self.lowerlegLength     = RightKnee.vector.length
            self.thighLength        = RightHip.vector.length
            
        else:
            self.lowerlegLength     = 0.0
            self.thighLength        = 0.0
            
        logger.debug("Done initializing %s", self.name)

    def __repr__(self):
        return f"<{self.__class__} self.name"
        
    @property
    def object(self):
        """Returns the Handle to manipulate the Armature in Blender."""
        return bpy.data.objects[self._object_id]
    
    @property
    def name(self):
        """Name of the Avatar"""
        return self.object.name
        
    def getPostureLegend(self):
        """Accesses the Default-Posture to retrieve the ordering of joint.id's 
        and channels."""
        
        idx = 0
        msg = []
        for joint in self.posture.Joints:
            for channel in joint.Channels:
                msg.append(f"{joint.ID}:{channel}")
                
        return msg
        
    def resetBoneMatrix(self, id=None):
        """Puts the IK Bones in Blender at the Position of their associated 
        Bones. This is important, since the ApplyPostureValues-Method does not 
        move IK-Bones."""

        if id is not None:
            if not id in self.ikConstraints.keys():
                id = self.effectorMap[id][1]
            ikid = self.ikConstraints[id].subtarget
            if(ikid is not None):
                logger.debug("Reset Position of IK Bone %s.", id)
                bone = self.object.pose.bones[id]
                ikbone = self.object.pose.bones[ikid]#[id+'IK'] # use Effector-Map
                ikbone.matrix = bone.matrix
        else:
            for name in self.ikConstraints.keys():
                self.resetBoneMatrix(name)
        
        return
        
    def ScaleMAvatarPosture(self, posture: tavatar.MAvatarPosture):
        """
        This function can scale the blender rig to the proper size of the 
        intermediate skeleton. 
        
        parameters:
            - posture : tavatar.MAvatarPosture - the zero posture of the intermediate 
                        skeleton. (e.g. from <MAvatarDescription>)
        """
        logger.debug("Call to ScaleMAvatarPosture")
        o = self.object
        armature = o.data
        
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        
        edit_bones = armature.edit_bones

        for b in o.pose.bones:
            b.rotation_mode="QUATERNION"
            b.rotation_quaternion = Quaternion((1,0,0,0))
            b.location = Vector((0,0,0))

        bpy.context.view_layer.update()

        def setGlobalRot(b, j, parent):
            #if not j.Parent is None:
            #    print("setGlobalRot", b.name, j.ID, parent.name)
            parent_rotation = Quaternion() if j.Parent is None else Quaternion(parent["globalRot"])#(b.parent["globalRot"])
            # global rotation of this joint
            rotation = parent_rotation @  MQuaternion2Quaternion(j.Rotation)
            b["globalRot"] = rotation
            
            # global position of this joint
            parent_pos = Vector() if j.Parent is None else parent.head #b.parent.head
            b.head = parent_pos + parent_rotation @ MVector2Vector(j.Position)
        
        for j in posture.Joints:
            # first iteration: set joint heads. 
            #logger.debug('set joint head for %s', j.ID)
            b = edit_bones[j.ID]
            parent = b.parent
            setGlobalRot(b, j, parent)
            if(j.ID in VIRTUAL_JOINTS):
                b_ = edit_bones[j.ID + "V"]
                b_["globalRot"] = b["globalRot"]
                b_.head = 1.0 * b.head
            
        def SetTail(b, child):
            if child is None:#len(b.children) == 0:
                # in case of a tip joint, set size to a very small value
                b.tail = b.head + Quaternion(b.parent["globalRot"]) @ Vector((0,0.01,0))
            else:
                # in case there is a child, due to the design of the intermediate skeleton, 
                # the first child is always the child were the joint is pointing to. 
                b.tail = child.head #b.children[0].head

        for j in posture.Joints:
            # second iteration: set joint tails
            b = edit_bones[j.ID]
            child = None
            if(j.ID in VIRTUAL_JOINTS):
                b_ = edit_bones[j.ID + "V"]
                SetTail(b, b_.children[0])
                b_.tail = 1.0 * b.tail
                #SetTail(b_, b_.children[0])
            else:
                if(len(b.children) > 0):
                    child = b.children[0]
                SetTail(b, child)
            

        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)    
        bpy.context.view_layer.update()


        for b in o.pose.bones:
            self.zero_matrix[b.name] = Matrix(b.matrix)
            if b.parent is None:
                self.base_matrix[b.name] = b.matrix.inverted()
            else:
                self.base_matrix[b.name] = (b.parent.matrix.inverted() @ b.matrix).inverted()
                
        self.resetBoneMatrix()
        return
        
    def ApplyMAvatarPostureValues(self, values: List[float]):
        """
        This function applies a set of posture values to the blender rig. 
        
        parameters:
            - values: list[float]
        
        """
        
        logger.debug("Call to ApplyMAvatarPostureValues")

        self.disableAllConstraints()
        i = 0
        for joint in self.posture.Joints:
            posebone = self.object.pose.bones[joint.ID]            
            t = Vector()
            q = Quaternion()
            
            
            # coordinate system transforms: 
            # translation (x,y,z) -> (-x, y, z)
            # quaternion (w, x, y, z) -> (-w, -x, y, z)
            for channel in joint.Channels: # refactor with dict?
                if channel == tavatar.MChannel.XOffset:
                    t.x = -values[i]
                elif channel == tavatar.MChannel.YOffset:
                    t.y = values[i]
                elif channel == tavatar.MChannel.ZOffset:
                    t.z = values[i]
                    
                elif channel == tavatar.MChannel.WRotation:
                    q.w = -values[i]
                elif channel == tavatar.MChannel.XRotation:
                    q.x = -values[i]
                elif channel == tavatar.MChannel.YRotation:
                    q.y = values[i]
                elif channel == tavatar.MChannel.ZRotation:
                    q.z = values[i]
                #logger.debug("Apply value %f to joint [%s] in channel %s", values[i], joint.ID, channel)
                i += 1

            # we can directly set the rotations and locations, due to the fact 
            # that we set up the blender rig exactly as the intermediate skeleton. 
            #logger.debug("from vector %s and Quaternion %s at bone %s", posebone.location, posebone.rotation_quaternion, posebone.name)
            #logger.debug("Apply vector %s and Quaternion %s to bone %s", t, q, posebone.name)

            if joint.ID in VIRTUAL_JOINTS:
                vpb = self.object.pose.bones[joint.ID + "V"]
                vpb.rotation_quaternion = Quaternion(q)
                vpb.location = Vector(t)
                posebone.rotation_quaternion = Quaternion()
                posebone.location = Vector()
            else:
                posebone.rotation_quaternion = Quaternion(q)
                posebone.location = Vector(t)

            
        return
    
    def ReadMAvatarPostureValues(self) -> List[float]:
        """
        This function reads intermediate skeleton rotation values from the 
        blender rig. 
        
        returns:
            - animation values : list[float]
        
        """
        
        logger.debug("Call to ReadMAvatarPostureValues")
        animationValues    = []
        matrices = {}
        
        #rwik = bpy.data.objects['lalala'].pose.bones['RightWrist']
        #logger.debug("Start of ReadMAvatarPostureValues: RightWrist at position: %s, %s", rwik.matrix.translation, rwik.rotation_quaternion)
        #for bone in self.object.pose.bones: # refactor!
        #    matrices[bone.name] = (Matrix(bone.matrix))
        
        #rwik = bpy.data.objects['lalala'].pose.bones['RightWrist']
        #logger.debug("Middle of ReadMAvatarPostureValues: RightWrist at position: %s, %s", rwik.matrix.translation, rwik.rotation_quaternion)
        #for bone in bpy.data.objects['lalala'].pose.bones:#self.object.pose.bones: # refactor!
        #    bone.matrix = matrices[bone.name]
            
        #logger.debug("End of ReadMAvatarPostureValues: RightWrist at position: %s, %s", rwik.matrix.translation, rwik.rotation_quaternion)
        bpy.context.view_layer.update()

        for joint in self.posture.Joints:
            jointid = joint.ID
            for vbone in VIRTUAL_JOINTS:
                jointid = jointid.replace(vbone, vbone + "V")
            matrix = bpy.data.objects['lalala'].convert_space(
                pose_bone=bpy.data.objects['lalala'].pose.bones[jointid],
                matrix=bpy.data.objects['lalala'].pose.bones[jointid].matrix, 
                from_space='WORLD', to_space='LOCAL'
            )
            q = matrix.to_quaternion()
            t = matrix.translation
            #if joint.ID=='RightWrist':
            #    logger.debug("loop of ReadMAvatarPostureValues: RightWrist at position: %s, %s", t, q)

            # coordinate system transforms: 
            # translation (x,y,z) -> (-x, y, z)
            # quaternion (w, x, y, z) -> (-w, -x, y, z)
            for channel in joint.Channels:
                if channel == tavatar.MChannel.XOffset:
                    animationValues.append(-t.x)
                elif channel == tavatar.MChannel.YOffset:
                    animationValues.append(t.y)
                elif channel == tavatar.MChannel.ZOffset:
                    animationValues.append(t.z)
                    
                elif channel == tavatar.MChannel.WRotation:
                    animationValues.append(-q.w)
                elif channel == tavatar.MChannel.XRotation:
                    animationValues.append(-q.x)
                elif channel == tavatar.MChannel.YRotation:
                    animationValues.append(q.y)
                elif channel == tavatar.MChannel.ZRotation:
                    animationValues.append(q.z)
                
            #logger.debug("Read vector %s and Quaternion %s to bone %s", t, q, posebone.name)
        
        #rwik = self.object.pose.bones['RightWrist']
        #pos = rwik.matrix.translation
        #rot = rwik.rotation_quaternion
        
        return animationValues
        
    def AddPositionConstraint(self, joint_in: str, target: Vector): # t -> Naming!
        """
            joint_in: target joint name (string)
            target       : Vector of scene coordinates. Its attributes are x, y and z
        """
        
        logger.debug("Call to AddPositionConstraint %s"%joint_in)
        
        ikTarget, ikConstraint, offset = self.effectorMap.get(joint_in, (None, None))
        if ikTarget is None:
            raise Exception(f"Unknown id for joint_in [{joint_in}]")
        
        self.enableIKConstraint(ikConstraint)
        
        # Blender pose bones: joint_in-related bones
        o           = self.object  # Blender's armature
        IKTarget      = o.pose.bones[self.ikConstraints[ikConstraint].subtarget] #o.pose.bones[ikTarget + "IK"]
        HandBone      = o.pose.bones[ikTarget] 
        
        # Set the IKTarget to the desired position
        IKTarget.matrix.translation    = target # In armature coordinates

        if("Wrist" in HandBone.name):
            self.enableIKConstraint("T1T2Joint")

        bpy.context.view_layer.update()

        # check distance
        # if("Wrist" in HandBone.name):
        #     direction = target - HandBone.matrix.translation
        #     spine_pos = o.pose.bones["PelvisCenter"].matrix.translation
        #     d2 = target - spine_pos
        #     if(direction.magnitude > 0.01):
        #         print("spine required %.3f"%(direction.magnitude), direction)
        #         self.AddPositionConstraint("T1T2Joint", goal)
        #         bpy.context.view_layer.update()
        #         i += 1
                

        
        # If the IK-Target is too low, then change the position of the root bone (PelvisCenter) to bend the legs 
        # if targetCoordinates.y < self.bendThreshold and joint_id in {'RightHand', 'LeftHand'}:
        #     self.croutch()
        
        return    

    def FixAtCurrentPosititionRotation(self, joint_in : str):
        logger.debug("Fix other joints current position and rotation. ")
        ikTarget, ikConstraint, offset = self.effectorMap.get(joint_in, (None, None))
        if ikTarget is None:
            raise Exception(f"Unknown id for joint_in [{joint_in}]")

        # Blender pose bones: joint_in-related bones
        o           = self.object  # Blender's armature
        IKTarget      = o.pose.bones[self.ikConstraints[ikConstraint].subtarget] #o.pose.bones[ikTarget + "IK"]
        HandBone      = o.pose.bones[ikTarget] 

        IKTarget.matrix = o.matrix_world @ HandBone.matrix
        
        self.enableIKConstraint(ikConstraint)
        return
    
    def getJointPosition(self, joint_id: str):
        return self.object.pose.bones[joint_id].head
        
    def croutch(self):
        self.enableIKConstraint('LeftAnkle')
        self.enableIKConstraint('RightAnkle')
        PelvisCenter.location.y        = -self.lowerlegLength # He jumps here
        deltaLegs                      = Vector((0, -self.thighLength, -self.lowerlegLength))
        RightAnkleIK.matrix.translation = (PelvisCenter.matrix @ Matrix.Translation(deltaLegs)).translation
        return
        
    def AddRotationConstraint(self, joint_id: str, rot: Union[Quaternion, Euler, Matrix]):
        """
            joint_id: target joint name (string)
            rot       : rotation, any of (Quaternion, Euler, Matrix)
        """
        
        #logger.debug(f"Call to AddRotationConstraint({joint_id}, {rot})")
        skeletonQ = Quaternion()
        if isinstance(rot, (Euler, Matrix)):
            rot = rot.to_quaternion()

        bpy.context.view_layer.update()
        ikTarget, ikConstraint, offset = self.effectorMap.get(joint_id, (None, None))
        if ikTarget is None:
            logger.warning("Unknown joint_id [%s]", joint_id)
            return
            
        self.enableCopyConstraint(ikTarget)
        bpy.context.view_layer.update()

        #blenderPoseBone = bpy.data.objects['lalala'].pose.bones[effector+"IK"]
        #logger.debug(f"rot: {rot}")
        
        for j in self.posture.Joints: # move to IKService
            if j.ID == ikTarget:
                #logger.debug(f"Rotating %s", j)
                for channel in j.Channels:
                    if   channel == tavatar.MChannel.WRotation:
                        skeletonQ.w = rot.w
                    elif channel == tavatar.MChannel.XRotation:
                        skeletonQ.x = rot.x
                    elif channel == tavatar.MChannel.YRotation:
                        skeletonQ.y = rot.y
                    elif channel == tavatar.MChannel.ZRotation:
                        skeletonQ.z = rot.z
        

        ikbone = self.object.pose.bones[self.ikConstraints[ikConstraint].subtarget] #bpy.data.objects['lalala'].pose.bones[ikTarget + "IK"]
        # backup translation component
        translation = Vector(ikbone.matrix.translation)
        # set rotation constraint, incorporate base-matrix to get the right rotation
        ikbone.matrix = skeletonQ.to_matrix().to_4x4() #@ ikbone.matrix_basis
        bpy.context.view_layer.update()
        # re-set translational component
        ikbone.matrix.translation = translation
        bpy.context.view_layer.update()

        #logger.debug(f"After: {blenderPoseBone.matrix}")
    
    def getJointRotation(self, joint_id: str):
        return self.object.pose.bones[joint_id].rotation_quaternion
    
    def solveIK(self):
        logger.debug("Call to solveIK")
        pass # bpy.ops.scene.update() # 
        
    def enableIKConstraint(self, name):
        self.resetBoneMatrix(name)
        constraint = self.ikConstraints.get(name, None)
        constraint.mute = False
        return
        
    def enableCopyConstraint(self, name):
        self.resetBoneMatrix(name)
        try:
            constraint = self.copyConstraints[name]
            constraint.mute = False
        except KeyError:
            logger.exception("Can't find Copy-Constraint %s", name)
            raise Exception("Can't find Copy-Constraint %s", name)
            
        return

    def disableAllConstraints(self):
        for name, constraint in self.ikConstraints.items():
            constraint.mute = True
        
        for name, constraint in self.copyConstraints.items():
            constraint.mute = True
        
        logger.debug("All known Constraints disabled.")
        return
        
