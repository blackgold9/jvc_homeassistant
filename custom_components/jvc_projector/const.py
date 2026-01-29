"""Constants for the jvc_projector integration."""

from jvcprojector import command

NAME = "JVC Projector"
DOMAIN = "jvc_projector"
MANUFACTURER = "JVC"

# Command mapping for coordinator and other components
COMMANDS = {
    "power": command.Power,
    "input": command.Input,
    "picture_mode": command.PictureMode,
    "laser_power": command.LaserPower,
    "light_power": command.LightPower,
    "eshift": command.EShift,
    "installation_mode": command.InstallationMode,
    "anamorphic": command.Anamorphic,
    "laser_dimming": command.DynamicControl,
    "content_type": command.ContentType,
    "hdr": command.Hdr,
    "hdmi_input_level": command.HdmiInputLevel,
    "hdmi_color_space": command.HdmiColorSpace,
    "color_profile": command.ColorProfile,
    "graphics_mode": command.GraphicMode,
    "color_space": command.ColorSpace,
    "motion_enhance": command.MotionEnhance,
    "clear_motion_drive": command.ClearMotionDrive,
    "hdr_processing": command.HdrProcessing,
    "resolution": command.Source,  # Using Source for resolution info
    "signal": command.Signal,
    "low_latency": command.LowLatencyMode,
    "lamp_time": command.LightTime,
}

# Sensor Keys
KEY_POWER = "power"
KEY_INPUT = "input"
KEY_PICTURE_MODE = "picture_mode"
KEY_LASER_POWER = "laser_power"
KEY_LASER_DIMMING = "laser_dimming"
KEY_LIGHT_POWER = "light_power"
KEY_ESHIFT = "eshift"
KEY_INSTALLATION_MODE = "installation_mode"
KEY_ANAMORPHIC = "anamorphic"
KEY_CONTENT_TYPE = "content_type"
KEY_HDR = "hdr"
KEY_HDMI_INPUT_LEVEL = "hdmi_input_level"
KEY_HDMI_COLOR_SPACE = "hdmi_color_space"
KEY_COLOR_PROFILE = "color_profile"
KEY_GRAPHICS_MODE = "graphics_mode"
KEY_COLOR_SPACE = "color_space"
KEY_MOTION_ENHANCE = "motion_enhance"
KEY_CLEAR_MOTION_DRIVE = "clear_motion_drive"
KEY_HDR_PROCESSING = "hdr_processing"
KEY_RESOLUTION = "resolution"
KEY_SIGNAL = "signal"
KEY_LOW_LATENCY = "low_latency"
KEY_LAMP_TIME = "lamp_time"
KEY_SOURCE = "signal"  # Source binary sensor uses signal status
KEY_LASER_VALUE = "laser_power"  # Mapping laser value to laser_power command
KEY_LASER_TIME = "lamp_time"  # Mapping laser time to lamp time (LightTime)

# Testing Keys

# Constants for states
ON = "on"
OFF = "off"
WARMING = "warming"
SIGNAL = "signal"
STANDBY = "standby"


# Helper to extract values
def _get_values(cls):
    excludes = {
        "category",
        "code",
        "depends",
        "describe",
        "limp_mode",
        "lookup",
        "name",
        "op_value",
        "operation",
        "operation_timeout",
        "parameter",
        "ref_value",
        "reference",
        "registry",
        "supports",
        "unload",
    }
    return [
        getattr(cls, a)
        for a in dir(cls)
        if not a.startswith("_")
        and isinstance(getattr(cls, a), str)
        and a not in excludes
    ]


# Value lists for sensors and selects
VAL_POWER = _get_values(command.Power)
VAL_HDR_CONTENT_TYPE = _get_values(command.ContentType)
VAL_HDR_MODES = _get_values(command.Hdr)
VAL_HDMI_INPUT_LEVEL = _get_values(command.HdmiInputLevel)
VAL_HDMI_COLOR_SPACE = _get_values(command.HdmiColorSpace)
VAL_GRAPHICS_MODE = _get_values(command.GraphicMode)
VAL_MOTION_ENHANCE = _get_values(command.MotionEnhance)
VAL_CLEAR_MOTION_DRIVE = _get_values(command.ClearMotionDrive)
VAL_FUNCTION_INPUT = _get_values(command.Input)
VAL_INSTALLATION_MODE = _get_values(command.InstallationMode)
VAL_ANAMORPHIC = _get_values(command.Anamorphic)
VAL_LASER_DIMMING = _get_values(command.DynamicControl)
VAL_ESHIFT = _get_values(command.EShift)
VAL_LIGHT_POWER = _get_values(command.LightPower)
VAL_PICTURE_MODE = _get_values(command.PictureMode)
# For toggle-like values (on/off)
VAL_TOGGLE = [command.Power.ON, command.Power.OFF]

# Remote commands mapping
REMOTE_COMMANDS = {
    "menu": command.Remote.MENU,
    "up": command.Remote.UP,
    "down": command.Remote.DOWN,
    "left": command.Remote.LEFT,
    "right": command.Remote.RIGHT,
    "ok": command.Remote.OK,
    "back": command.Remote.BACK,
    "mpc": command.Remote.MPC,
    "hide": command.Remote.HIDE,
    "info": command.Remote.INFO,
    "input": command.Remote.INPUT,
    "cmd": command.Remote.CMD,
    "advanced_menu": command.Remote.ADVANCED_MENU,
    "picture_mode": command.Remote.PICTURE_MODE,
    "color_profile": command.Remote.COLOR_PROFILE,
    "lens_control": command.Remote.LENS_CONTROL,
    "setting_memory": command.Remote.SETTING_MEMORY,
    "gamma_settings": command.Remote.GAMMA_SETTINGS,
    "hdmi_1": command.Remote.HDMI1,
    "hdmi_2": command.Remote.HDMI2,
    "mode_1": command.Remote.MODE_1,
    "mode_2": command.Remote.MODE_2,
    "mode_3": command.Remote.MODE_3,
    "lens_ap": command.Remote.LENS_APERTURE,
    "gamma": command.Remote.GAMMA,
    "color_temp": command.Remote.COLOR_TEMP,
    "natural": command.Remote.NATURAL,
    "cinema": command.Remote.CINEMA,
    "anamo": command.Remote.ANAMORPHIC,
    "3d_format": command.Remote.V3D_FORMAT,
}
