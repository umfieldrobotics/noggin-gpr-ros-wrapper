# noggin-gpr-ros-wrapper

This ROS 1 driver was developed to aid the work conducted for ["Learning Surface Terrain Classifications from Ground Penetrating Radar"](https://arxiv.org/abs/2404.09094), to be presented at CVPR 2024 Perception Beyond the Visible Spectrum Workshop. If you use this code, please cite:

```
@inproceedings{sheppard2024,
  title={Learning Surface Terrain Classifications from Ground Penetrating Radar},
  author={Sheppard, Anja and Brown, Jason and Renno, Nilton and Skinner, Katherine A},
  booktitle={Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition},
  pages={3047--3055},
  year={2024}
}
```

The driver was adapted from https://github.com/alexbaikovitz/noggin_gpr_node and then adapted for Python 3 and ROS Melodic.

## Usage

This driver was written for the Noggin 500 MHz GPR sensor with the SpidarSDK software. In order to use this wrapper, your sensor needs to be in SDK mode. More information can be found in the [sensor manual](https://www.sensoft.ca/wp-content/uploads/2020/03/Noggin_User_Guide.pdf).

To use this wrapper, first create a ROS workspace and clone this repo into it. Compile the workspace, ensuring that you include the custom ROS message and the node script. Inside the `gpr_read_node.py` script, change any parameters to match your usage (for example, the GPR IP address, which appears on the sensor upon boot).

To run:

Ensure that the GPR is turned on and connected via ethernet to the computer that you are running the wrapper on.

```
$ roscore
$ rosrun noggin-gpr-ros-wrapper gpr_read_node.py
```

After the GPR boots up, you should see messages on the `/gpr/traces` topic!
