import datetime
import geode
import geode_osdf

start = datetime.datetime(2026, 9, 13, 3, 0, tzinfo=datetime.UTC)
end   = datetime.datetime(2026, 9, 13, 9, 0, tzinfo=datetime.UTC)

dt = geode.get("atms_n20", start, end)

meta = dt["/MetaData"].ds
obs = dt["/ObsValue"].ds

latitude = meta["latitude"].values
longitude = meta["longitude"].values
brightness_temperature = obs["brightnessTemperature"].values

print("latitude:", latitude.shape, latitude.dtype)
print("longitude:", longitude.shape, longitude.dtype)
print("brightnessTemperature:", brightness_temperature.shape,
      brightness_temperature.dtype)

result = geode_osdf.make_frame(
    latitude,
    longitude,
    brightness_temperature,
)

print("OSDF:", result)

assert result["numRows"] == latitude.shape[0]
assert result["numCols"] == 24

print("PASS")
