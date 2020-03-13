#!/usr/bin/env python
#
# 
# Copyright 2020 Spectric Labs Inc (www.spectric.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import termios
import struct
import logging
import binascii
import tty
import time
import serial
import math
import construct as c
import numpy

###############################################################################
# Enumerations
PacketTypes = dict(
    CONTROL = 0x00,
    CHANNEL = 0x01,
    SPEECH = 0x02,
)

PacketType = c.Enum(
    c.Byte,
    **PacketTypes
)

# Table 31
ControlPacketFields = dict(
    PKT_CHANNEL0 = 0x40,
    PKT_ECMODE = 0x05,
    PKT_DCMODE = 0x06,
    PKT_COMPAND = 0x32,
    PKT_RATET = 0x09,
    PKT_RATEP = 0x0A,
    PKT_INIT = 0x0B,
    PKT_LOWPOWER = 0x10,
    PKT_CODECCFG = 0x38,
    PKT_CODECSTART = 0x2A,
    PKT_CODECSTOP = 0x2B,
    PKT_CHANFMT = 0x15,
    PKT_SPCHFMT = 0x16,
    PKT_PRODID = 0x30,
    PKT_VERSTRING = 0x31,
    PKT_READY = 0x39,
    PKT_HALT = 0x36,
    PKT_RESET = 0x33,
    PKT_RESETSOFTCFG = 0x34,
    PKT_GETCFG = 0x36,
    PKT_READCFG = 0x37,
    PKT_PARITYMODE = 0x3F,
    PKT_WRITE_I2C = 0x44,
    PKT_CLFCODECRESET = 0x46,
    PKT_SETCODECRESET = 0x47,
    PKT_DISCARDCODEC = 0x48,
    PKT_DELAYNUS = 0x49,
    PKT_DELAYNNS = 0x4A,
    PKT_RTSTHRESH = 0x4E,
    PKT_GAIN =0x4B
)

ControlPacketField = c.Enum(
    c.Byte,
    **ControlPacketFields
)

###############################################################################
# Generic Constructs
GeneralPacket = c.Struct(
    "START_BYTE" / c.Const(b'\x61'),
    "LENGTH" / c.Int16ub,
    "TYPE" / PacketType,
    "FIELDS" / c.Byte[c.this.LENGTH] 
)

# Table 12 AMBE-3000R Version 2.2
ECMODE_IN = c.FlagsEnum(c.Int16ub,
    NS_ENABLE  = (0x1 << 6),
    CP_SELECT  = (0x1 << 7),
    CP_ENABLE  = (0x1 << 8),
    ES_ENABLE  = (0x1 << 9),
    DTX_ENABLE = (0x1 << 11),
    TD_ENABLE  = (0x1 << 12),
    EC_ENABLE  = (0x1 << 13),
    TS_ENABLE  = (0x1 << 14),
)

# Table 13 AMBE-3000R Version 2.2
ECMODE_OUT = c.FlagsEnum(c.Int16ub,
    VOICE_ACTIVE  = (0x1 << 1),
    TONE_FRAME   = (0x1 << 15)
)

# Table 14 AMBE-3000R Version 2.2
DCMODE_IN = c.FlagsEnum(c.Int16ub,
    LOST_FRAME  = (0x1 << 2),
    CNI_FRAME   = (0x1 << 3),
    CP_SELECT   = (0x1 << 7),
    CP_ENABLE   = (0x1 << 8),
    TS_ENABLE   = (0x1 << 14),
)

# Table 15 AMBE-3000R Version 2.2
DCMODE_OUT = c.FlagsEnum(c.Int16ub,
    VOICE_ACTIVE  = (0x1 << 1),
    DATA_INVALID  = (0x1 << 5),
    TONE_FRAME    = (0x1 << 15)
)

###############################################################################
# Control Messages
ReadCfgCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_READCFG"))
)

ResetCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_RESET"))
)

InitCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_INIT"))
)

InitResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_INIT")),
    "RESULT" / c.Byte
)


ReadyResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_READY"))
)

HaltResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_HALT"))
)

ResetSoftCfgCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_RESETSOFTCFG")),
    "CFG0" / c.FlagsEnum(c.Byte,
        CP_SELECT=0x80,
        CP_ENABLE=0x40,
        NS_ENABLE=0x20,
        DTX_ENABLE=0x08,
        IF_SELECT2=0x04,
        IF_SELECT1=0x02,
        IF_SELECT0=0x01,
    ),
    "CFG1" / c.FlagsEnum(c.Byte,
        ES_ENABLE=0x80,
        EC_ENABLED=0x40,
        RATE5=0x20,
        RATE4=0x10,
        RATE3=0x08,
        RATE2=0x04,
        RATE1=0x02,
        RATE0=0x01,
    ),
    "CFG2" / c.FlagsEnum(c.Byte,
        PARITY_ENABLE=0x10,
        S_COM_RATE2=0x04,
        S_COM_RATE1=0x02,
        S_COM_RATE0=0x01,
    ),
    "MASK0" / c.FlagsEnum(c.Byte,
        CP_SELECT=0x80,
        CP_ENABLE=0x40,
        NS_ENABLE=0x20,
        DTX_ENABLE=0x08,
        IF_SELECT2=0x04,
        IF_SELECT1=0x02,
        IF_SELECT0=0x01,
    ),
    "MASK1" / c.FlagsEnum(c.Byte,
        ES_ENABLE=0x80,
        EC_ENABLED=0x40,
        RATE5=0x20,
        RATE4=0x10,
        RATE3=0x08,
        RATE2=0x04,
        RATE1=0x02,
        RATE0=0x01,
    ),
    "MASK2" / c.FlagsEnum(c.Byte,
        PARITY_ENABLE=0x10,
        S_COM_RATE2=0x04,
        S_COM_RATE1=0x02,
        S_COM_RATE0=0x01,
    ),
)

DcModeCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_DCMODE")),
    "DCMODE_IN" / DCMODE_IN
)

DcModeResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_DCMODE")),
    "RESULT" / c.Byte,
)

ChanFmtCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_CHANFMT")),
    "CHANFMT" / c.Int16ub,
)

ChanFmtResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_CHANFMT")),
    "RESULT" / c.Byte,
)

SpchFmtCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_SPCHFMT")),
    "SPCHFMT" / c.Int16ub,
)

SpchFmtResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_SPCHFMT")),
    "RESULT" / c.Byte,
)

EcmodeCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_ECMODE")),
    "ECMODE_IN" / ECMODE_IN
)

EcmodeCmdResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_ECMODE")),
    "RESULT" / c.Byte,
)

InitCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_INIT")),
    "INIT" / c.FlagsEnum(c.Byte,
        echo_canceller=0x4,
        decoder_init=0x2,
        encoder_init=0x1,
    )
)

ProdIdCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_PRODID"))
)

ProdIdResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_PRODID")),
    "PRODID" / c.CString("utf8")
)

VersionCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_VERSTRING"))
)

VersionResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_VERSTRING")),
    "VERSTRING" / c.CString("utf8")
)

RateTCmd = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_RATET")),
    "RATE_IDX" / c.Byte
)

RateTResp = c.Struct(
    "FIELD_ID" / c.Const(ControlPacketField.build("PKT_RATET")),
    "RESULT" / c.Byte
)

###############################################################################
# Speech Messages
SpeechPCM = c.Struct(
    "FIELD_ID" / c.Const(b'\x00'),
    "NUM_SAMPLES" / c.Byte, # 156 - 164
    "DATA" / c.Array(c.this.NUM_SAMPLES, c.Int16ub)
)

SpeechCMODE = c.Struct(
    "FIELD_ID" / c.Const(b'\x02'),
    "CMODE_IN" / ECMODE_IN
)

SpeechDCMODE = c.Struct(
    "FIELD_ID" / c.Const(b'\x02'),
    "DCMODE_OUT" / DCMODE_OUT
)

SpeechTONE = c.Struct(
    "FIELD_ID" / c.Const(b'\x08'),
    "TONE_IDX" / c.Byte,
    "TONE_AMPLITUDE" / c.Byte,
)


SpeechPCMPacket = c.Struct(
    "FIELD_ID" / c.Const(b'\x40'),
    "SPEECHD" / c.Optional(SpeechPCM),
    "CMODE" / c.Optional(SpeechCMODE),
    "TONE" / c.Optional(SpeechTONE),
)

SpeechPCMResp = c.Struct(
    "FIELD_ID" / c.Const(b'\x00'),
    "NUM_SAMPLES" / c.Byte, # 156 - 164
    "DATA" / c.Array(c.this.NUM_SAMPLES, c.Int16ub),
    "BYTES" / c.Computed(
        lambda this: struct.pack('H'*this.NUM_SAMPLES, *this.DATA)
    ),
    "CMODE" / c.Optional(SpeechDCMODE)
)

###############################################################################
# Channel Messages

ChannelCMODE = c.Struct(
    "FIELD_ID" / c.Const(b'\x02'),
    "CMODE_IN" / c.FlagsEnum(c.Int16ub,
        LOST_FRAME  = 0x0004,
        CNI_FRAME   = 0x0008,
        TS_ENABLE   = 0x4000,
    )
)

ChannelECMODE = c.Struct(
    "FIELD_ID" / c.Const(b'\x02'),
    "ECMODE_OUT" / ECMODE_OUT
)

ChannelTONE = c.Struct(
    "FIELD_ID" / c.Const(b'\x08'),
    "TONE_IDX" / c.Byte,
    "TONE_AMPLITUDE" / c.Byte,
)

ChanD = c.Struct(
    "FIELD_ID" / c.Const(b'\x01'),
    "NUM_BITS" / c.Byte, # 40 - 192
    "DATA" / c.Array(lambda this: math.ceil(this.NUM_BITS / 8), c.Byte)
)

ChanD4 = c.Struct(
    "FIELD_ID" / c.Const(b'\x17'),
    "NUM_BITS" / c.Byte, # 40 - 192
    "DATA" / c.Array(lambda this: math.ceil(this.NUM_BITS / 8), c.Byte)
)
ChannelSamples = c.Struct(
    "FIELD_ID" / c.Const(b'\x03'),
    "NUM_BITS" / c.Byte, # 40 - 192
    "DATA" / c.Array(lambda this: math.ceil(this.NUM_BITS / 8), c.Byte)
)

ChannelPacket = c.Struct(
    "FIELD_ID" / c.Const(b'\x40'),
    "CHAND" / c.Optional(ChanD),
    "CHAND4" / c.Optional(ChanD4),
    "CMODE" / c.Optional(ChannelCMODE),
    "TONE" / c.Optional(ChannelTONE),
    "NUM_SAMPLES" / c.Optional(c.Byte), # 156 - 164
)

ChannelDefaultVocoderPacket = c.Struct(
    "CHAND" / c.Optional(ChanD),
    "CHAND4" / c.Optional(ChanD4),
    "CMODE" / c.Optional(ChannelCMODE),
    "TONE" / c.Optional(ChannelTONE),
    "NUM_SAMPLES" / c.Optional(c.Byte), # 156 - 164
)

ChannelResp = c.Struct(
    "FIELD_ID" / c.Const(b'\x01'),
    "NUM_BITS" / c.Byte,
    "DATA" / c.Array(lambda this: math.ceil(this.NUM_BITS / 8), c.Byte),
    "BYTES" / c.Computed(
        lambda this: c.lib.integers2bytes(this.DATA)
    ),
    "CMODE" / c.Optional(ChannelECMODE),
)

DV3K_START_BYTE = b'\x61'

DV3K_TYPE_CONTROL = b'\x00'
DV3K_TYPE_AMBE = b'\x01'
DV3K_TYPE_AUDIO = b'\x02'

DV3K_CONTROL_RATET = b'\x09'
DV3K_CONTROL_RATEP = b'\x0A'
DV3K_CONTROL_INIT = b'\x0B'

DV3K_CONTROL_PRODID = b'\x30'
DV3K_CONTROL_VERSTRING = b'\x31'
DV3K_CONTROL_RESET = b'\x33'
DV3K_CONTROL_READY = b'\x39'
DV3K_CONTROL_CHANFMT = b'\x15'

SERIAL_BAUD=460800 

class AmbeServer(object):
    """
    https://www.dvsinc.com/manuals/AMBE-3000R_manual.pdf

    Section 6.5
    """

    def __init__(self, device=None, logger=None):
        if device is None:
            for dev in os.listdir("/dev/serial/by-id/"):
                if dev.startswith("usb-FTDI_ZUM_AMBE3000_"):
                    device = os.path.join("/dev/serial/by-id/", dev)
                    break

        self.device = device

        self.log = logger
        if self.log is None:
            self.log = logging.getLogger("Modem")


    def open_serial(self):
        """
        Opens the serial port to the device
        """
        self.port = serial.Serial(
            self.device,
            baudrate=SERIAL_BAUD,
            timeout=5.0,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False)
	
        self.port.flushInput()
        self.port.flushOutput()

    def send_packet(self, pkt_type, fields, resp_type, resp):
        """
        Sends a command packet to the device.
        """
        cmd = GeneralPacket.build(
            dict(
                LENGTH=len(fields),
                TYPE=pkt_type,
                FIELDS=fields,

            )
        )

        self.log.debug("writing %s", binascii.hexlify(cmd))
        
        numout = self.port.write(cmd)
        if numout != len(cmd):
            self.log.warning("Failed to write command")

        frame_type, data = self.get_response()
        if frame_type != PacketType.build(resp_type):
            self.log.warning("Unexpected frame_type returned")
            return False

        try:
            return resp.parse(data)
        except c.ConstError:
            self.log.warning("Failed to parse data with %s", resp)
            return None

    def get_response(self):
        """
        Reads a response from the device
        """
        d = self.port.read(1)
        offset = 1
        if not d:
            self.log.warning("Read nothing")
            return None, None

        # Get the start of frame, or nothing at all
        if d != DV3K_START_BYTE:
            self.log.warning("Invalid MMDVM frame start %02X", d)
            return None, None

        # Get the length of the frame
        d_len = struct.unpack('>H', self.port.read(2))[0]
        offset += 2

        frame_type = self.port.read(1)
        offset += 1

        if d_len == 0:
            d_len = self.read_short()
            offset += 2

        data = self.port.read(d_len)

        self.log.debug("received %s %s %s", d_len, binascii.hexlify(frame_type), binascii.hexlify(data))
        return frame_type, data

    ###########################################################################
    def init(self, **kwargs):
        logging.info("sending init")
        echo_canceller = kwargs.get("echo_canceller", False)
        encoder_init   = kwargs.get("encoder_init", True)
        decoder_init   = kwargs.get("decoder_init", True)

        init = InitCmd.build(
            dict(
                INIT=dict(
                    echo_canceller=echo_canceller,
                    decoder_init=decoder_init,
                    encoder_init=encoder_init,
                )
            )
        )

        resp = self.send_packet(
            PacketType.CONTROL,
            init,
            "CONTROL",
            InitResp
        )

        if resp == None:
            self.log.warning("DV3K not ready after init")
            return False
        
        return resp.RESULT == 0x00

    def reset(self):
        logging.info("sending reset")
        reset = ResetCmd.build(dict())

        resp = self.send_packet(
            PacketType.CONTROL,
            reset,
            "CONTROL",
            ReadyResp
        )

        if resp == None:
            self.log.warning("DV3K not ready after reset")
            return False
        
        return True

    def get_prod_id(self):
        logging.info("sending get_prod_id")
        prodid = ProdIdCmd.build(dict())

        resp = self.send_packet(
            PacketType.CONTROL,
            prodid,
            "CONTROL",
            ProdIdResp
        )

        if resp == None:
            self.log.warning("DV3K failed to get prodid")
            return None
        
        return resp.PRODID

    def get_version(self):
        logging.info("sending get_version")
        prodid = VersionCmd.build(dict())

        resp = self.send_packet(
            PacketType.CONTROL,
            prodid,
            "CONTROL",
            VersionResp
        )

        if resp == None:
            self.log.warning("DV3K failed to get version")
            return None
        
        return resp.VERSTRING

    def set_ratet(self, rate_idx):
        logging.info("sending set_ratet")
        ratet = RateTCmd.build(
            dict(
                RATE_IDX=rate_idx
            )
        )

        resp = self.send_packet(
            PacketType.CONTROL,
            ratet,
            "CONTROL",
            RateTResp
        )

        if resp == None:
            self.log.warning("DV3K failed to set ratet")
            return None
        
        return resp.RESULT == 0

    def set_chanfmt(self, ecmode, samples):
        logging.info("sending set_chanfmt")
        chanfmt = 0x0
        if ecmode == "always":
            chanfmt |= 0x01
        elif ecmode == "onchange":
            chanfmt |= 0x02

        if samples == "always":
            chanfmt |= 0x10
        elif samples == "ondifference":
            chanfmt |= 0x20
        elif samples == "not160":
            chanfmt |= 0x30
            
        cmd = ChanFmtCmd.build(
            dict(
                CHANFMT=chanfmt
            )
        )

        resp = self.send_packet(
            PacketType.CONTROL,
            cmd,
            "CONTROL",
            ChanFmtResp
        )

        if resp == None:
            self.log.warning("DV3K failed to set command")
            return None
        
        return resp.RESULT == 0

    def set_spchfmt(self, dcmode, samples):
        logging.info("sending set_spchfmt")
        spchfmt = 0x0
        if dcmode == "always":
            spchfmt |= 0x01
        elif dcmode == "onchange":
            spchfmt |= 0x02

        if samples == "always":
            spchfmt |= 0x10
        elif samples == "ondifference":
            spchfmt |= 0x20
        elif samples == "not160":
            spchfmt |= 0x3
            
        cmd = SpchFmtCmd.build(
            dict(
                SPCHFMT=spchfmt
            )
        )

        resp = self.send_packet(
            PacketType.CONTROL,
            cmd,
            "CONTROL",
            SpchFmtResp
        )

        if resp == None:
            self.log.warning("DV3K failed to set command")
            return None
        
        return resp.RESULT == 0

    def set_ecmode(self, **kwargs):
        logging.info("sending set_ecmode")
        cmd = EcmodeCmd.build(
            dict(
                ECMODE_IN=kwargs
            )
        )

        resp = self.send_packet(
            PacketType.CONTROL,
            cmd,
            "CONTROL",
            EcmodeCmdResp
        )

        if resp == None:
            self.log.warning("DV3K failed to set command")
            return None
        
        return resp.RESULT == 0

    def set_dcmode(self, **kwargs):
        logging.info("sending set_dcmode")
        cmd = DcModeCmd.build(
            dict(
                DCMODE_IN=kwargs
            )
        )

        resp = self.send_packet(
            PacketType.CONTROL,
            cmd,
            "CONTROL",
            DcModeResp
        )

        if resp == None:
            self.log.warning("DV3K failed to set command")
            return None
        
        return resp.RESULT == 0

    def get_readcfg(self):
        cmd = bytearray.fromhex("61 00 01 00 37")
        raise NotImplementedError

    def encode_speech(self, pcm16):
        logging.info("sending spch_pkt")
        assert len(pcm16) == 160
        
        cmd = SpeechPCMPacket.build(
            dict(
                SPEECHD = dict(
                    NUM_SAMPLES=160,
                    DATA=pcm16,
                
                ),
                CMODE=None,
                TONE=None,
            )
        )
        
        resp = self.send_packet(
            PacketType.SPEECH,
            cmd,
            "CHANNEL",
            ChannelResp
        )

        if resp == None:
            self.log.warning("DV3K failed to send speech")
            return None
        
        return resp

    def encode_tone(self, pcm16, tone_idx, tone_amp):
        speech = SpeechPCMPacket.build(
            dict(
                SPEECHD = dict(
                    NUM_SAMPLES=160,
                    DATA=pcm16,

                ),
                CMODE=dict(
                    CMODE_IN=dict(
                        TS_ENABLE=True,
                    ),
                ),
                TONE=dict(
                    TONE_IDX = tone_idx,
                    TONE_AMPLITUDE = tone_amp 
                ),
            )
        )
        
        resp = self.send_packet(
            PacketType.SPEECH,
            speech,
            "CHANNEL",
            ChannelResp
        )

        if resp == None:
            self.log.warning("DV3K failed to send speech")
            return None
        
        return resp

    def decode_ambe(self, ambe):
        assert len(ambe) == 9

        chan = ChannelDefaultVocoderPacket.build(
            dict(
                CHAND = dict(
                    NUM_BITS=72,
                    DATA=ambe,

                ),
                CHAND4=None,
                CMODE=None,
                TONE=None,
                NUM_SAMPLES=None
            )
        )
        
        resp = self.send_packet(
            PacketType.CHANNEL,
            chan,
            "SPEECH",
            SpeechPCMResp
        )

        if resp == None:
            self.log.warning("DV3K failed to send channel")
            return None
        
        return resp

    def open(self):
        self.open_serial()
