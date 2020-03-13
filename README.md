# Usage

Construct the object

```
import ambeserver
svr = ambeserver.AmbeServer()
```

Open a connection

```
svr.open()
svr.reset()
svr.init()
```

Set some parameters

```
svr.set_chanfmt("always", "always")
svr.set_spchfmt("always", "never")
svr.set_ecmode(NS_ENABLE=True, DTX_ENABLE=True)
```

Decode AMBE audio

```
aud = svr.decode_ambe(ambe_bytes)
```

Encode AMBE to audio

```
ambe_bytes = svr.encode_speech(samples)
```

# Notes

The USB interface API is the DVSI-3000R chip API

https://www.qsl.net/kb9mwr/projects/dv/codec/AMBE-3000R_manual.pdf
