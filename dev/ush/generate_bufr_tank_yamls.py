#!/usr/bin/env python3
"""Generate bufr-query mapping YAMLs (bAAA_xxBBB.yaml) for NCEP BUFR tanks.

Each YAML maps every query that show_queries.x lists for a tank. Variable names
come from NAMES below, then the curated configs in src/spoc/dump/config/atmosphere,
then the BUFR table description. Units come from the table embedded in the tank.

Mnemonics starting with "." are left out, with a comment in the YAML, because the
bufr-query parser cannot handle them yet.

The ingest writer appends along Location, so other dimensions must not change size
between files. Each repeated sequence in a tank is therefore stored in one of these
ways:

- One variable-length vertical or long sequence becomes rows, using group_by_variable.
- Channels and fixed sequences of LONG_SEQUENCE or more stay as dimensions.
- Other sequences become numbered variables, using the fixed count from the BUFR table
  or a limit based on bufr_tank_sequence_sizes.yaml. Anything over the limit is dropped.
- Extra long variable-length sequences stay as dimensions, with a warning in the YAML.
- Raw report text stays in pieces for tanks without levels, for the ingestor to join.
  Tanks with levels do not store it, and file names are never stored.

Tanks that share a dataset in table_a_mapping.yaml get the same set of variables, because
the store cannot append data whose variables differ. See share_variables.

A tank with several unrelated profiles (MULTI_PROFILE_TANKS) gets one mapping per profile,
bAAA_xxBBB_<profile>.yaml, each stored as its own dataset. For STACKED_TANKS the profiles are
stacked as rows of one dataset, labelled by MetaData/recordType.

Inputs, one file per tank named bAAA_xxBBB.txt. Run these for each tank, inside the
GEODE container:

    show_queries.x <tank_root>/bAAA/xxBBB > <queries_dir>/bAAA_xxBBB.txt
    gettab <tank_root>/bAAA/xxBBB > <tables_dir>/bAAA_xxBBB.txt

usage: generate_bufr_tank_yamls.py <queries_dir> <tables_dir> <geode_root> <out_dir> [tank ...]

Example, for one tank:

    generate_bufr_tank_yamls.py queries tables . configs/bufr/tanks b002_xx009
"""

import collections
import copy
import glob
import json
import os
import re
import sys

import yaml

QUERY_RE = re.compile(r"^(\d+)d[ \t]+(\w+)[ \t]+(\S+)[ \t]*(.*)$", re.M)
DIM_RE = re.compile(r"^[ \t]+(\d+)d[ \t]+(\S+)[ \t]*$", re.M)

# Calendar pieces consumed by the datetime variable
TIME_KEYS = [
    ("year", "YEAR"),
    ("month", "MNTH"),
    ("day", "DAYS"),
    ("hour", "HOUR"),
    ("minute", "MINU"),
]

# Receipt-time pieces combined into MetaData/receiptTime
RECEIPT_KEYS = [
    ("year", "RCYR"),
    ("month", "RCMO"),
    ("day", "RCDY"),
    ("hour", "RCHR"),
    ("minute", "RCMI"),
]

# Mnemonic -> (group or None for class-based, name). Takes priority over curated names.
NAMES = {
    # identification
    "SBPI": (None, "stationaryBuoyIdentifier"),
    "BPID": (None, "buoyPlatformIdentifier"),
    "SHPC8": (None, "shipCallSign"),
    "SMID": (None, "shipOrMobileStationIdentifier"),
    "WMOB": (None, "wmoBlockNumber"),
    "WMOS": (None, "wmoStationNumber"),
    "WMOR": (None, "wmoRegionNumber"),
    "STSN": (None, "stationName"),
    "LSTN": (None, "stationLongName"),
    "SSTN": (None, "radarStationIdentifier"),
    "ACID": (None, "aircraftFlightNumber"),
    "ACRN": (None, "aircraftTailNumber"),
    "OBSVR": (None, "observerIdentification"),
    "TOST": (None, "stationType"),
    "A4ME": (None, "measuringEquipmentType"),
    "RATP": (None, "radiosondeType"),
    "TIWM": (None, "windInstrumentationType"),
    "GCLONG": (None, "generatingCenterLong"),
    "GSES": (None, "generatingSubCenter"),
    "SOFTV": (None, "softwareVersion"),
    "SWID": (None, "softwareIdentification"),
    "DBID": (None, "databaseIdentification"),
    "GPTI": (None, "gridPointIdentifier"),
    "OSQN": (None, "observationSequenceNumber"),
    "ORBN": (None, "orbitNumber"),
    "CORN": (None, "correctedReportIndicator"),
    # receipt / bulletin / raw text
    "RCTS": (None, "receiptTimeSignificance"),
    "BUHD": (None, "bulletinHeader"),
    "BORG": (None, "bulletinOriginator"),
    "BULTIM": (None, "bulletinTime"),
    "BBB": (None, "bulletinBBB"),
    "RRSTG": (None, "rawReportString"),
    "FNSTG": (None, "fileNameString"),
    "PRVSTG": (None, "providerIdentifier"),
    "SPRVSTG": (None, "subProviderIdentifier"),
    # time periods
    "TSIG": (None, "timeSignificance"),
    "TPHR": (None, "timePeriodHours"),
    "TPMI": (None, "timePeriodMinutes"),
    "TPMO": (None, "timePeriodMonths"),
    "LTDS": (None, "longTimePeriodSeconds"),
    "FOST": (None, "firstOrderStatistics"),
    "UALNHR": (None, "radiosondeLaunchHour"),
    "UALNMN": (None, "radiosondeLaunchMinute"),
    # vertical coordinates
    "HSALG": (None, "heightOfSensorAboveGround"),
    "HSAWS": (None, "heightOfSensorAboveWater"),
    "HBMSL": (None, "heightOfBarometerAboveMeanSeaLevel"),
    "DBLS": (None, "depthBelowLandSurface"),
    "DBSS": (None, "depthBelowSeaSurface"),
    "FLVL": (None, "flightLevel"),
    "PSAL": (None, "pressureAltitude"),
    "VSIG": (None, "verticalSoundingSignificance"),
    "VSSO": (None, "verticalSignificanceSurface"),
    "VSAT": ("MetaData", "verticalSignificanceSatellite"),
    "VSNWP": (None, "verticalSignificanceNwp"),
    # thermodynamics
    "TMDB": ("ObsValue", "airTemperature"),
    "TMDBST": ("ObsValue", "airTemperature"),
    "TMDP": ("ObsValue", "dewPointTemperature"),
    "TMWB": ("ObsValue", "wetBulbTemperature"),
    "REHU": ("ObsValue", "relativeHumidity"),
    "MXTM": ("ObsValue", "maximumTemperature"),
    "MITM": ("ObsValue", "minimumTemperature"),
    "PRES": ("ObsValue", "airPressure"),
    "PMSL": ("ObsValue", "pressureReducedToMeanSeaLevel"),
    "ALSE": ("ObsValue", "altimeterSetting"),
    "3HPC": ("ObsValue", "pressureChange3Hour"),
    "24PC": ("ObsValue", "pressureChange24Hour"),
    "CHPT": ("ObsValue", "pressureTendencyCharacteristic"),
    "GP07": ("ObsValue", "geopotential07"),
    "GP10": ("ObsValue", "geopotential10"),
    # wind
    "UWND": ("ObsValue", "windEastward"),
    "VWND": ("ObsValue", "windNorthward"),
    "WCMP": ("ObsValue", "windUpward"),
    "UMWV": ("ObsValue", "modelWindEastward"),
    "VWMV": ("ObsValue", "modelWindNorthward"),
    "MXGS": ("ObsValue", "maximumWindGustSpeed"),
    "MXGD": ("ObsValue", "maximumWindGustDirection"),
    "PKWDSP": ("ObsValue", "peakWindSpeed"),
    "PKWDDR": ("ObsValue", "peakWindDirection"),
    # weather / precipitation / snow
    "HOVI": ("ObsValue", "horizontalVisibility"),
    "VTVI": ("ObsValue", "verticalVisibility"),
    "PRWE": ("ObsValue", "presentWeather"),
    "PSW1": ("ObsValue", "pastWeather1"),
    "PSW2": ("ObsValue", "pastWeather2"),
    "TOPC": ("ObsValue", "totalPrecipitation"),
    "TP01": ("ObsValue", "totalPrecipitationPast1Hour"),
    "TP03": ("ObsValue", "totalPrecipitationPast3Hours"),
    "TP06": ("ObsValue", "totalPrecipitationPast6Hours"),
    "TP12": ("ObsValue", "totalPrecipitationPast12Hours"),
    "TP24": ("ObsValue", "totalPrecipitationPast24Hours"),
    "TOSD": ("ObsValue", "totalSnowDepth"),
    "DOFS": ("ObsValue", "depthOfFreshSnow"),
    "SWEM": ("ObsValue", "snowWaterEquivalent"),
    # land / road
    "STEM": ("ObsValue", "soilTemperature"),
    "STEMH": ("ObsValue", "soilTemperature"),
    "SLMT": ("ObsValue", "soilMoistureTension"),
    "RDTM": ("ObsValue", "roadTemperature"),
    # ocean
    "SST1": ("ObsValue", "seaSurfaceTemperature"),
    "SST0": ("ObsValue", "seaSurfaceTemperature"),
    "SALN": ("ObsValue", "salinity"),
    "HOWV": ("ObsValue", "waveHeight"),
    "POWV": ("ObsValue", "wavePeriod"),
    "HOWW": ("ObsValue", "windWaveHeight"),
    "POWW": ("ObsValue", "windWavePeriod"),
    "HOSW": ("ObsValue", "swellWaveHeight"),
    "POSW": ("ObsValue", "swellWavePeriod"),
    "DOSW": ("ObsValue", "swellWaveDirection"),
    "SGWH": ("ObsValue", "significantWaveHeight"),
    # radar
    "VOID": (None, "radarVolumeIdentifier"),
    "SCID": (None, "radarScanIdentifier"),
    "VOCP": ("MetaData", "volumeCoveragePattern"),
    "ANAZ": (None, "antennaAzimuthAngle"),
    "ANEL": (None, "antennaElevationAngle"),
    "DIST": (None, "distanceToGateCenter"),
    "DIST125M": (None, "distanceToGateCenter125m"),
    "DMVR": ("ObsValue", "dopplerMeanRadialVelocity"),
    "DVSW": ("ObsValue", "dopplerVelocitySpectralWidth"),
    "HREF": ("ObsValue", "horizontalReflectivity"),
    "HNQV": ("MetaData", "highNyquistVelocity"),
    "QCRW": ("QualityMarker", "radialWind"),
    "QCRF": ("QualityMarker", "reflectivity"),
    # quality marks
    "QMPR": ("QualityMarker", "pressure"),
    "QMAT": ("QualityMarker", "airTemperature"),
    "QMDD": ("QualityMarker", "moisture"),
    "QMWN": ("QualityMarker", "wind"),
    "QMGP": ("QualityMarker", "geopotential"),
    "QMST": ("QualityMarker", "seaSurfaceTemperature"),
    "QMWH": ("QualityMarker", "waveHeight"),
    "QCD": ("QualityMarker", "fslQcData"),
    "QCA": ("QualityMarker", "fslQcApplied"),
    "QCR": ("QualityMarker", "fslQcResults"),
    "SHRV": ("QualityMarker", "shefRevisionFlag"),
    "SHQL": ("QualityMarker", "shefQualifierFlag"),
}

# Repeated-sequence mnemonic -> dimension name
DIM_NAMES = {
    "RCPTIM": "ReceiptTime",
    "BID": "Bulletin",
    "RAWRPT": "RawReportChunk",
    "FILENAME": "FileNameChunk",
    "PRVID": "ProviderChunk",
    "SPRVID": "SubProviderChunk",
    "NL2RF": "ReflectivityGate",
    "NL2RW": "RadialWindGate",
    "UARLV": "Level",
    "UARLVB": "HighResolutionLevel",
    "UARID": "RadiosondeIdentification",
    "UARDCS": "RadiosondeDiagnostic",
    "UACLD": "RadiosondeCloud",
    "WPLVL": "ProfilerLevel",
    "PFLEV": "ProfileLevel",
    "OZPROFSQ": "OzoneProfileLevel",
    "BSYBCLD": "BaseCloudLayer",
    "BSYSCLD": "SignificantCloudLayer",
    "BSYDCLD": "DirectionalCloudLayer",
    "CLDSQ1": "CloudLayer",
    "CLOUDSQ1": "CloudLayer2",
    "BSYPCP2": "PrecipitationPeriod",
    "BSYWND2": "WindPeriod",
    "MNTOPCSQ": "TotalPrecipitationPeriod",
    "CNTOPCSQ": "ContinuousPrecipitationPeriod",
    "MNRDWYSQ": "RoadwaySensor",
    "MNSORDSQ": "SolarRadiationPeriod",
    "MNDOFSSQ": "FreshSnowPeriod",
    "MNSOMTSQ": "SoilMoistureSensor",
    "WAVSQ3": "WaveSpectralBand",
    "AMBIGWND": "AmbiguousWind",
    "ASCATSG0": "ScatterometerBeam",
    "CORNSQ": "CorrectionSequence",
    "MDPT": "ProviderMetadata",
}

# BUFR Table B class -> group for mnemonics without an explicit name
METADATA_CLASSES = {
    "000", "001", "002", "003", "004", "005", "006", "007", "008", "009",
    "025", "026", "027", "028", "029", "030", "031", "035", "050", "058",
}  # fmt: skip

UNITS = {
    "M": "m", "METERS": "m", "METER": "m", "GPM": "gpm",
    "M/SEC": "m s-1", "M/S": "m s-1", "M S**-1": "m s-1", "METERS/SEC": "m s-1",
    "METERS/SECOND": "m s-1", "METER/SECOND": "m s-1",
    "K": "K", "KELVIN": "K", "DEGREES KELVIN": "K",
    "PA": "Pa", "PASCALS": "Pa",
    "DEGREE": "degree", "DEGREES": "degree", "DEGREE TRUE": "degree", "DEGREES TRUE": "degree",
    "DEGREE(N+,S-)": "degree_north", "DEGREE(E+,W-)": "degree_east", "DEGREE**2": "degree2",
    "%": "%", "PERCENT": "%",
    "DB": "dB", "DECIBELS": "dB", "DECIBLES": "dB",
    "DECIBLES/DEGREE": "dB degree-1", "DECIBLES/METER": "dB m-1",
    "HZ": "Hz", "S": "s", "SECOND": "s", "SECONDS": "s",
    "MINUTE": "min", "MINUTES": "min", "HOUR": "h", "HOURS": "h",
    "DAY": "day", "MONTH": "month", "YEAR": "year",
    "KG": "kg", "KG/KG": "kg kg-1",
    "KG/M**2": "kg m-2", "KG/(M**2)": "kg m-2", "KG/METER**2": "kg m-2", "KG/(METER**2)": "kg m-2",
    "KG M**-2 S**-1": "kg m-2 s-1", "KG/((METER**2)*SECOND)": "kg m-2 s-1",
    "JOULE/METER**2": "J m-2", "JOULE M**-2": "J m-2",
    "WATT/METER**2": "W m-2", "WATT M**-2": "W m-2",
    "WM**(-3)SR**(-1)": "W m-3 sr-1", "WM**(-2)SR**(-1)": "W m-2 sr-1",
    "(METERS/SECOND)**2": "m2 s-2", "METERS**2/SECOND": "m2 s-1", "METERS**3/SECOND": "m3 s-1",
    "METERS**2/HZ": "m2 Hz-1", "M**3": "m3", "M**-2": "m-2",
    "(M**2/3)(S**-1)": "m2/3 s-1", "1/S": "s-1",
    "MM/HOUR": "mm h-1", "SIEMENS/M": "S m-1", "AMPS": "A", "VOLTS": "V", "V": "V", "RAD": "rad",
    "PART PER THOUSAND": "1e-3", "PARTS/1000": "1e-3",
    "EIGHTHS OF A KM": "125 m", "DU": "DU", "N-UNITS": "N-units",
    "W M**-2 SR**-1 M": "W m-2 sr-1 m", "W M**-2 SR**-1 CM": "W m-2 sr-1 cm",
    "W M**-2 SR**-1 UM**-1": "W m-2 sr-1 um-1", "M**-1": "m-1", "KG M**-3": "kg m-3",
    "HERTZ": "Hz", "(MM) (H**-1)": "mm h-1",
    "LOG(M**-3)": "log(m-3)", "LOG/M": "log(m-1)", "LOG METER**-2": "log(m-2)",
}  # fmt: skip
UNITLESS = {"CODE TABLE", "FLAG TABLE", "CCITT IA5", "NUMERIC", ""}

UNKNOWN_UNITS = collections.Counter()
DESC_WIDTH = 55

# Replications that are single values in practice, taken as the first element
SINGLE_SEQUENCES = {"RCPTIM", "BID"}
# Text stored as repeated 8-character pieces, with the number of pieces to keep
TEXT_SEQUENCES = {"PRVID": 2, "SPRVID": 2}
DROPPED_SEQUENCES = {"FILENAME": "source file name"}
RAW_REPORT_SEQUENCE = "RAWRPT"
# Sequences that are vertical levels or range gates even when they are short
VERTICAL_SEQUENCES = {"UARLV", "UARLVB", "WPLVL", "PFLEV", "OZPROFSQ", "NL2RF", "NL2RW", "NP3RW"}
# A sequence this long is flattened or kept as a dimension instead of numbered
LONG_SEQUENCE = 20
MAX_NUMBERED = 20
MAX_NUMBERED_WITH_GROUP = 50
# Tanks holding several unrelated profiles, one mapping per profile: tank -> profile -> sequence
MULTI_PROFILE_TANKS = {
    "b003_xx010": {"bending_angle": "ROSEQ1", "refractivity": "ROSEQ3", "retrieval": "ROSEQ4"},
    "b001_xx103": {
        "surface": None,
        "temperature_salinity": "IDMSMDBS/BBYSTSL",
        "currents": "MOCMDBDS/BBYCURR",
        "wave_spectra": "SPCTRWAV/BBYSPWV",
    },
}
# Tanks whose profiles are stacked as rows of one dataset, labelled by MetaData/recordType,
# instead of one dataset per profile
STACKED_TANKS = {"b001_xx103"}
# Sequences not stored for one tank: tank -> sequence -> reason
TANK_DROPPED_SEQUENCES = {
    "b008_xx019": {"RPSEQ3": "BUFR data-present bitmap for quality values that are empty"},
}
# A mnemonic no subset contains, for variables a tank does not have
ABSENT_MNEMONIC = "ABSENT"


def camel(text):
    """'MEAN WIND SPEED (1 KM)' -> 'meanWindSpeed1Km'"""
    words = re.findall(r"[A-Za-z0-9]+", text.replace("'", ""))
    if not words:
        return ""
    out = words[0].lower() + "".join(w[0].upper() + w[1:].lower() for w in words[1:])
    return out if out[0].isalpha() else "v" + out


def title(text):
    """Keep mixed-case descriptions; title-case the all-caps ones from Table B."""
    text = " ".join(text.split())
    if text.upper() != text:
        return text
    return " ".join(w.capitalize() if w.isalpha() else w for w in text.split(" "))


def yaml_str(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def read_tables(path):
    """Parse gettab output into Table A descriptions and per-mnemonic Table B info."""
    table_a, table_b = {}, {}
    with open(path, errors="replace") as handle:
        for line in handle:
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) < 3:
                continue
            if re.fullmatch(r"A\d{5}", cols[1]):
                table_a[cols[0]] = cols[2]
            elif re.fullmatch(r"\d{6}", cols[1]):
                table_b.setdefault(cols[0], {}).update(fxy=cols[1], desc=cols[2])
            elif len(cols) >= 5 and re.fullmatch(r"-?\d+", cols[1]) and cols[3].isdigit():
                table_b.setdefault(cols[0], {})["units"] = cols[4]
    return table_a, table_b


def read_curated(geode_root):
    """Harvest mnemonic -> (group, name) from the curated spoc configs."""
    votes = collections.defaultdict(collections.Counter)
    patterns = [f"{geode_root}/src/spoc/dump/config/atmosphere/*.yaml"]
    for pattern in patterns:
        for path in glob.glob(pattern):
            if "prepbufr" in path:
                continue
            with open(path) as handle:
                config = yaml.safe_load(handle)
            if "bufr" not in config or "encoder" not in config:
                continue
            queries = {
                k: v["query"]
                for k, v in config["bufr"]["variables"].items()
                if isinstance(v, dict) and isinstance(v.get("query"), str)
            }
            for entry in config["encoder"]["variables"]:
                query = queries.get(entry["source"].split("/")[-1])
                if query and "/" in entry["name"]:
                    mnem = re.sub(r"[\[{]\d+[\]}]", "", query).split("/")[-1].strip("[]")
                    votes[mnem][tuple(entry["name"].split("/", 1))] += 1
    return {m: c.most_common(1)[0][0] for m, c in votes.items()}


def read_table_a_mapping(geode_root):
    with open(f"{geode_root}/configs/bufr/table_a_mapping.yaml") as handle:
        return yaml.safe_load(handle)


class Query:
    def __init__(self, dim, dtype, path, desc):
        self.dim = int(dim)
        self.dtype = dtype
        self.path = path  # relative to the subset, may include [n]
        self.desc = desc
        leaf = path.split("/")[-1]
        match = re.fullmatch(r"(.+)\[(\d+)\]", leaf)
        self.mnemonic = match.group(1) if match else leaf
        self.index = int(match.group(2)) if match else None
        self.parents = path.split("/")[:-1]
        self.group = self.name = self.units = self.long_name = None

    @property
    def query(self):
        return f"*/{self.path}"


def parse_listing(path):
    with open(path, errors="replace") as handle:
        text = handle.read()
    if "Queries:" not in text:
        raise ValueError(f"no queries in {path}")
    # BUFRLIB diagnostics can precede the listing on stdout
    subsets = text.split("Available subset variants:")[1].split("Total number")[0].split("\n")
    subsets = [s.strip() for s in subsets if s.strip()]
    if len(subsets) != 1:
        raise ValueError(f"expected one subset in {path}, found {subsets}")
    dims = [p for d, p in DIM_RE.findall(text.split("Queries:")[0]) if p != "*"]
    queries = [
        Query(d, t, p.split("/", 1)[1], desc.strip())
        for d, t, p, desc in QUERY_RE.findall(text.split("Queries:")[1])
        if "/" in p
    ]
    return subsets[0], dims, queries


def normalize_units(raw):
    raw = (raw or "").strip()
    if raw in UNITLESS:
        return None
    if raw in UNITS:
        return UNITS[raw]
    UNKNOWN_UNITS[raw] += 1
    return raw


def describe(query, table_b, curated):
    """Assign group, base name, long name and units to a query."""
    mnem = query.mnemonic
    info = table_b.get(mnem, {})

    query.group, query.name = resolve_name(mnem, info, table_b, curated)
    query.long_name = title(query.desc or info.get("desc", mnem))
    query.units = normalize_units(info.get("units"))


def resolve_name(mnem, info, table_b, curated):
    group, name = NAMES.get(mnem, (None, None))
    if name is None and mnem in curated:
        group, name = curated[mnem]
    if name is None:
        text = info.get("desc", mnem)
        if len(text) >= DESC_WIDTH and " " in text:
            text = text.rsplit(" ", 1)[0]  # clipped by the table column; drop the partial word
        text = re.sub(r"\bSDMEDIT\b|\bQUIPS\b", " ", text)
        name = camel(text) or camel(mnem)
    if group is None:
        fxy = info.get("fxy", "")
        klass = fxy[:3]
        if klass == "033":
            group = "QualityMarker"
        elif klass in METADATA_CLASSES or not fxy:
            group = "MetaData"
        else:
            group = "ObsValue"
    return group, name


def suffix(seq):
    return seq[0].upper() + seq[1:].lower()


def uniquify(queries, reserved):
    """Make names unique: repeated-mnemonic index, then enclosing sequence, then mnemonic."""
    taken = set(reserved)

    def groups():
        table = collections.defaultdict(list)
        for query in queries:
            table[query.name].append(query)
        return table

    # First resolve clashes between different mnemonics sharing one name (e.g. TMDB / TMDBST)
    for name, members in groups().items():
        mnemonics = sorted({m.mnemonic for m in members})
        if len(mnemonics) > 1:
            for member in members:
                if member.mnemonic != mnemonics[0]:
                    member.name = f"{name}{re.sub(r'[^A-Za-z0-9]', '', member.mnemonic)}"

    # Then indexed duplicates of the same mnemonic under one parent
    for name, members in groups().items():
        if len(members) > 1:
            for member in members:
                if member.index is not None:
                    member.name = f"{name}{member.index}"

    # Then the same mnemonic in different sequences; the outermost keeps the plain name
    for name, members in groups().items():
        if len(members) > 1:
            members = sorted(members, key=lambda m: (len(m.parents), m.path))
            for member in members[1:] if not members[0].parents else members:
                seq = re.sub(r"[^A-Za-z0-9]", "", "".join(suffix(p) for p in member.parents[-1:]))
                member.name = f"{name}{seq}"

    for query in queries:
        base = query.name
        count = 2
        while query.name in taken:
            query.name = f"{base}{count}"
            count += 1
        taken.add(query.name)


def concrete_dim_paths(dim_paths, queries):
    """Map each listed path to the paths queries really use, e.g. */QCPRMS -> */QCPRMS[1]."""
    actual = collections.defaultdict(list)
    for query in queries:
        for depth in range(1, len(query.parents) + 1):
            path = "*/" + "/".join(query.parents[:depth])
            generic = re.sub(r"\[\d+\]", "", path)
            if path not in actual[generic]:
                actual[generic].append(path)
    return [path for listed in dim_paths for path in actual.get(listed, [])]


def read_replications(path):
    """Parse a gettab listing into sequence -> (kind, fixed count) from Table D."""
    replications = {}
    with open(path, errors="replace") as handle:
        for line in handle:
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) != 2:
                continue
            for mnem, count in re.findall(r'"([A-Z0-9]+)"(\d+)', cols[1]):
                replications[mnem] = ("fixed", int(count))
            for mnem in re.findall(r"\{([A-Z0-9]+)\}", cols[1]):
                replications[mnem] = ("delayed", None)
            for mnem in re.findall(r"\(([A-Z0-9]+)\)", cols[1]):
                replications.setdefault(mnem, ("delayed", None))
            for mnem in re.findall(r"<([A-Z0-9]+)>", cols[1]):
                replications[mnem] = ("fixed", 1)
    return replications


def sequence_of(path):
    return re.sub(r"\[\d+\]", "", path.split("/")[-1])


class Plan:
    """How each repeated sequence in a tank is stored."""

    def __init__(self):
        self.group_path = None
        self.keep = {}  # path -> (dimension name, channel query or None, varies)
        self.number = {}  # path -> count
        self.drop = {}  # path -> reason


def plan_sequences(dim_paths, queries, sizes, replications, tank_dropped=None):
    """Choose group_by, kept dimension or numbered variables for each sequence."""
    plan = Plan()
    dropped_sequences = {**DROPPED_SEQUENCES, **(tank_dropped or {})}
    paths = concrete_dim_paths(dim_paths, queries)
    channels = {
        path: next(
            (q for q in queries if q.mnemonic == "CHNM" and q.index is None
             and "/".join(["*"] + q.parents) == path), None)
        for path in paths
    }  # fmt: skip

    def size(path):
        return sizes.get(sequence_of(path), 0)

    def nested(path):
        return any(path.startswith(other + "/") for other in paths)

    candidates = [
        path for path in paths
        if not nested(path) and channels[path] is None
        and replications.get(sequence_of(path), ("delayed",))[0] == "delayed"
        and sequence_of(path) not in SINGLE_SEQUENCES | set(TEXT_SEQUENCES)
        and sequence_of(path) not in dropped_sequences and sequence_of(path) != RAW_REPORT_SEQUENCE
        and (sequence_of(path) in VERTICAL_SEQUENCES or size(path) >= LONG_SEQUENCE)
    ]  # fmt: skip
    if candidates:
        plan.group_path = max(
            candidates, key=lambda p: (sequence_of(p) in VERTICAL_SEQUENCES, size(p), p)
        )

    used = {"Location"}

    def dimension_name(path, source):
        leaf = path.split("/")[-1]
        match = re.fullmatch(r"(.+)\[(\d+)\]", leaf)
        seq, index = (match.group(1), match.group(2)) if match else (leaf, "")
        if source is not None and "Channel" not in used:
            name = "Channel"
        else:
            name = (DIM_NAMES.get(seq) or suffix(re.sub(r"[^A-Za-z0-9]", "", seq))) + index
        base, count = name, 2
        while name in used:
            name = f"{base}{count}"
            count += 1
        used.add(name)
        return name

    for path in paths:
        if path == plan.group_path:
            continue
        seq = sequence_of(path)
        kind, fixed = replications.get(seq, ("delayed", None))
        if seq in dropped_sequences:
            plan.drop[path] = dropped_sequences[seq]
        elif seq == RAW_REPORT_SEQUENCE:
            if plan.group_path is None:
                plan.keep[path] = ("RawReportChunk", None, True)
                used.add("RawReportChunk")
            else:
                plan.drop[path] = "raw report text, not stored for tanks with levels"
        elif channels[path] is not None:
            plan.keep[path] = (dimension_name(path, channels[path]), channels[path], False)
        elif seq in SINGLE_SEQUENCES:
            plan.number[path] = 1
        elif seq in TEXT_SEQUENCES:
            plan.number[path] = TEXT_SEQUENCES[seq]
        elif kind == "fixed" and fixed >= LONG_SEQUENCE:
            plan.keep[path] = (dimension_name(path, None), None, False)
        elif kind == "fixed":
            plan.number[path] = fixed
        elif size(path) >= LONG_SEQUENCE:
            plan.keep[path] = (dimension_name(path, None), None, True)
        else:
            plan.number[path] = min(MAX_NUMBERED, max(2, 2 * size(path)))

    # bufr-query cannot group by one sequence while another stays a repeated dimension
    if plan.group_path is not None:
        for path, (_name, source, varies) in list(plan.keep.items()):
            count = 2 * size(path) if varies else replications[sequence_of(path)][1]
            if source is None and count <= MAX_NUMBERED_WITH_GROUP:
                del plan.keep[path]
                plan.number[path] = count
        if plan.keep:
            plan.keep[plan.group_path] = (dimension_name(plan.group_path, None), None, True)
            plan.group_path = None

    # A dimension nested in a fixed-length sequence gets one dimension per element.
    # A variable-length parent cannot have a stable set of those, so read its first element.
    for path in plan.keep:
        for parent in plan.number:
            if path.startswith(parent + "/") and replications.get(sequence_of(parent), ("delayed",))[0] != "fixed":
                plan.number[parent] = 1
    return plan


def expand_query(query, plan):
    """Return the stored variables for a query, numbering any flattened sequences."""
    segments = query.path.split("/")
    expansions = [([], [])]
    for depth, segment in enumerate(segments):
        path = "*/" + "/".join(segments[: depth + 1])
        if path in plan.drop:
            return []
        count = plan.number.get(path) if depth < len(segments) - 1 else None
        if count is None:
            expansions = [(parts + [segment], nums) for parts, nums in expansions]
        else:
            expansions = [
                (parts + [f"{segment}{{{n}}}"], nums + ([n] if count > 1 else []))
                for parts, nums in expansions
                for n in range(1, count + 1)
            ]
    out = []
    for parts, nums in expansions:
        item = copy.copy(query)
        item.path = "/".join(parts)
        if nums:
            item.name = query.name + "_".join(str(n) for n in nums)
            item.long_name = f"{query.long_name} ({', '.join(str(n) for n in nums)})"
        out.append(item)
    return out


def pick_coordinate(queries, top_names):
    """Prefer a Location-level latitude/longitude, else the first element of a sequence."""
    for mnem in top_names:
        for query in queries:
            if query.mnemonic == mnem and not query.parents and query.index is None:
                return query, query.query
    for mnem in top_names:
        for query in queries:
            if query.mnemonic == mnem and query.index is None and query.dim == 2:
                return None, f"*/{'/'.join(query.parents)}{{1}}/{mnem}"
    return None, None


def build(tank, subset, dim_paths, queries, table_a, table_b, curated, mapping, sizes, replications,
          profile=None, profile_sequence=None):  # fmt: skip
    # bufr-query's QueryParser segfaults on "."-prefixed mnemonics, so they cannot be mapped
    unparsable = [q for q in queries if q.mnemonic.startswith(".")]
    queries = [q for q in queries if not q.mnemonic.startswith(".")]
    for query in queries:
        describe(query, table_b, curated)

    # dateTime: Location-level calendar mnemonics (first occurrence when repeated)
    time_lines, time_used, time_notes = {}, [], []
    for key, mnem in TIME_KEYS:
        candidates = [q for q in queries if q.mnemonic == mnem and not q.parents]
        candidates.sort(key=lambda q: q.index or 0)
        if candidates:
            time_lines[key] = candidates[0].query
            time_used.append(candidates[0])
        else:
            # bufr-query requires the key; an absent mnemonic only warns and reads as 0
            time_lines[key] = f"*/{mnem}"
            time_notes.append(f"{mnem} is not in this subset; {key} is treated as 0")
    seconds = [q for q in queries if q.mnemonic in ("SECO", "SECW") and not q.parents]
    seconds.sort(key=lambda q: (q.mnemonic != "SECO", q.index or 0))
    if seconds:
        time_lines["second"] = seconds[0].query
        # keep sub-second precision available if the datetime truncates it
        if seconds[0].dtype != "float":
            time_used.append(seconds[0])

    remaining = [q for q in queries if q not in time_used]

    lat_query, lat_path = pick_coordinate(remaining, ["CLATH", "CLAT"])
    lon_query, lon_path = pick_coordinate(remaining, ["CLONH", "CLON"])
    if profile_sequence:
        # Use the location of each level; the report's location becomes a reference point
        for mnemonics, reference in ((("CLATH", "CLAT"), "referenceLatitude"), (("CLONH", "CLON"), "referenceLongitude")):
            level = [q for q in remaining if q.mnemonic in mnemonics and "/".join(q.parents) == profile_sequence]
            if level:
                top = next((q for q in remaining if q.mnemonic in mnemonics and not q.parents), None)
                if top is not None:
                    top.name = reference
                if reference == "referenceLatitude":
                    lat_query, lat_path = level[0], level[0].query
                else:
                    lon_query, lon_path = level[0], level[0].query
    if lat_path is None or lon_path is None:
        raise ValueError(f"{tank}: no latitude/longitude")
    remaining = [q for q in remaining if q not in (lat_query, lon_query)]

    # receiptTime replaces the separate calendar fields when the full set is present
    receipt_parts = {}
    for key, mnem in RECEIPT_KEYS:
        found = [q for q in remaining if q.mnemonic == mnem and q.index is None]
        if len(found) == 1:
            receipt_parts[key] = found[0]
    has_receipt = len(receipt_parts) == len(RECEIPT_KEYS) and (
        len({tuple(q.parents) for q in receipt_parts.values()}) == 1
    )
    if has_receipt:
        remaining = [q for q in remaining if q not in receipt_parts.values()]

    reserved = {"timestamp", "latitude", "longitude", "receiptTime"}
    uniquify(remaining, reserved)

    said = next((q for q in remaining if q.mnemonic == "SAID" and q.dim == 1 and not q.parents and q.index is None), None)  # fmt: skip
    plan = plan_sequences(dim_paths, remaining, sizes, replications, TANK_DROPPED_SEQUENCES.get(tank))
    dropped = [q for q in remaining if not expand_query(q, plan)]
    remaining = [item for q in remaining for item in expand_query(q, plan)]
    names = set(reserved)
    for query in remaining:
        base, count = query.name, 2
        while query.name in names:
            query.name = f"{base}_{count}"
            count += 1
        names.add(query.name)
    if has_receipt:
        for query in receipt_parts.values():
            if query.parents:
                query.path = query.path.replace(f"{query.parents[0]}/", f"{query.parents[0]}{{1}}/", 1)
    group_key = None
    if plan.group_path is not None:
        prefix = plan.group_path[2:] + "/"
        direct = [q for q in remaining if q.path.startswith(prefix) and "/" not in q.path[len(prefix):]]
        if not direct:
            raise ValueError(f"{tank}: no variable to group {plan.group_path} by")
        group_key = direct[0].name
    if profile:
        said = None  # split by dataset_splits.yaml in the ingestor instead
    dims = []
    names_by_path = {query.path: query for query in remaining}
    for path, (name, source, varies) in plan.keep.items():
        parent = next((p for p in plan.number if path.startswith(p + "/")), None)
        if parent is None:
            dims.append((name, path, source, varies))
            continue
        count = plan.number[parent]
        for n in range(1, count + 1):
            written = path.replace(f"{parent}/", f"{parent}{{{n}}}/", 1)
            element_source = None
            if source is not None:
                element_source = names_by_path[source.path.replace(f"{parent[2:]}/", f"{parent[2:]}{{{n}}}/", 1)]
            dims.append((f"{name}{n}" if count > 1 else name, written, element_source, varies))
    # ---- bufr section
    out = ["bufr:", "  subsets:", f"    - {subset}", ""]
    if group_key:
        out += ["  # One row per element of this sequence", f"  group_by_variable: {group_key}", ""]
    out.append("  variables:")
    if dropped:
        out.append("    # Not mapped: see the sequence notes in dev/ush/generate_bufr_tank_yamls.py")
        out += [f"    #   {q.query}" for q in dropped]
        out.append("")
    if unparsable:
        out.append('    # Not mapped: bufr-query cannot parse these "."-prefixed mnemonics')
        out += [f"    #   {q.query}" for q in unparsable]
        out.append("")
    out.append("    # MetaData")
    out += ["    timestamp:", "      datetime:"]
    for note in time_notes:
        out.append(f"        # {note}")
    for key, value in time_lines.items():
        out.append(f'        {key}: "{value}"')
    out.append("")
    if has_receipt:
        out += ["    receiptTime:", "      datetime:"]
        out += [f'        {key}: "{q.query}"' for key, q in receipt_parts.items()]
        out.append("")
    out += ["    latitude:", f'      query: "{lat_path}"', ""]
    out += ["    longitude:", f'      query: "{lon_path}"', ""]

    order = {"MetaData": 0, "ObsValue": 1, "QualityMarker": 2}
    ordered = sorted(remaining, key=lambda q: order.get(q.group, 3))
    current = "MetaData"
    for query in ordered:
        if query.group != current:
            current = query.group
            out.append(f"    # {current}")
        out += [f"    {query.name}:", f'      query: "{query.query}"', ""]

    if said is not None:
        # No map: a mapped split silently drops satellites that are not listed
        out += ["  splits:", "    satId:", "      category:", f"        variable: {said.name}", ""]

    # ---- encoder section
    out.append("encoder:")
    if dims:
        out.append("  dimensions:")
        for name, path, source, varies in dims:
            if varies and name != "RawReportChunk":
                out.append("    # Variable length: appending can fail if the size changes")
            out.append(f"    - name: {name}")
            if source is not None:
                out.append(f"      source: variables/{source.name}")
            out.append(f'      path: "{path}"')
        out.append("")

    cat, sub = int(tank[1:4]), int(tank[7:10])
    entry = (mapping.get(cat) or {}).get("local subtypes", {}).get(sub)
    category = (mapping.get(cat) or {}).get("category")
    desc = table_a.get(subset) or f"NCEP BUFR tank {tank[:4]}/{tank[5:]}"
    globs = [("description", title(desc))]
    if category:
        globs.append(("dataCategory", category))
    if entry:
        globs.append(("dataset", f"{entry['dataset']}_{profile}" if profile and tank not in STACKED_TANKS else entry["dataset"]))
        globs.append(("dataFormat", entry["format"]))
        globs.append(("restricted", str(entry["restricted"]).lower()))
    if tank in STACKED_TANKS:
        globs.append(("recordType", profile))
    globs += [
        ("bufrCategory", f"{cat:03d}"),
        ("bufrLocalSubcategory", f"{sub:03d}"),
        ("source", "U.S. National Weather Service, National Centers for Environmental Prediction (NCEP)"),
        ("sourceFiles", f"NCEP BUFR Tank - {tank[:4]}/{tank[5:]} {subset}"),
        ("converter", "bufr-query"),
    ]  # fmt: skip
    out.append("  globals:")
    for name, value in globs:
        out += [f'    - name: "{name}"', "      type: string", f"      value: {yaml_str(str(value))}", ""]

    out += ["  variables:", "    # MetaData"]
    out += ['    - name: "MetaData/dateTime"', "      source: variables/timestamp",
            '      longName: "Datetime"', '      units: "seconds since 1970-01-01T00:00:00Z"', ""]  # fmt: skip
    if has_receipt:
        out += ['    - name: "MetaData/receiptTime"', "      source: variables/receiptTime",
                '      longName: "Receipt Time"', '      units: "seconds since 1970-01-01T00:00:00Z"', ""]  # fmt: skip
    out += ['    - name: "MetaData/latitude"', "      source: variables/latitude",
            '      longName: "Latitude"', '      units: "degree_north"', "      range: [-90, 90]", ""]  # fmt: skip
    out += ['    - name: "MetaData/longitude"', "      source: variables/longitude",
            '      longName: "Longitude"', '      units: "degree_east"', ""]  # fmt: skip
    current = "MetaData"
    for query in ordered:
        if query.group != current:
            current = query.group
            out.append(f"    # {current}")
        out += [f'    - name: "{query.group}/{query.name}"', f"      source: variables/{query.name}",
                f"      longName: {yaml_str(query.long_name)}"]  # fmt: skip
        if query.units:
            out.append(f'      units: "{query.units}"')
        out.append("")
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n", {"said": said is not None, "dims": len(dims), "vars": len(ordered) + 3 + has_receipt,
                                   "mapped": entry is not None, "subset": subset,
                                   "dataset": (f"{entry['dataset']}_{profile}" if profile and tank not in STACKED_TANKS else entry["dataset"]) if entry else None,
                                   "unparsable": [q.query for q in unparsable],
                                   "group": plan.group_path}  # fmt: skip


def _rename_variable(text, old_full, new_full):
    """Rename a variable in generated YAML text, in the bufr and encoder sections."""
    old_key, new_key = old_full.split("/", 1)[1], new_full.split("/", 1)[1]
    text = re.sub(rf"^    {re.escape(old_key)}:$", f"    {new_key}:", text, flags=re.M)
    text = re.sub(rf"variables/{re.escape(old_key)}$", f"variables/{new_key}", text, flags=re.M)
    text = text.replace(f'name: "{old_full}"', f'name: "{new_full}"')
    text = re.sub(rf"^(  group_by_variable|        variable): {re.escape(old_key)}$",
                  rf"\1: {new_key}", text, flags=re.M)  # fmt: skip
    return text


def _entries(text):
    """Return the parsed YAML and {encoder name: bufr variable definition and metadata}."""
    config = yaml.safe_load(text)
    entries = {}
    for item in config["encoder"]["variables"]:
        key = item["source"].split("/")[-1]
        entries[item["name"]] = {
            "key": key, "bufr": config["bufr"]["variables"][key],
            "units": item.get("units"), "long": item["longName"],
        }  # fmt: skip
    return config, entries


def _majority(values):
    counts = collections.Counter(values)
    return sorted(counts, key=lambda v: (-counts[v], len(v), v))[0]


def _absent_prefix(config, source_config, source_query):
    """Find where a placeholder must sit so its shape matches this tank's layout."""
    group_key = config["bufr"].get("group_by_variable")
    if group_key:
        return config["bufr"]["variables"][group_key]["query"].rsplit("/", 1)[0]
    dimensions = {d["name"]: d["path"] for d in config["encoder"].get("dimensions") or []}
    for dim in source_config["encoder"].get("dimensions") or []:
        if source_query and source_query.startswith(dim["path"] + "/"):
            if dim["name"] == "RawReportChunk" and dim["name"] not in dimensions:
                return "*"  # the ingestor stores an empty rawReport for these
            if dim["name"] not in dimensions:
                raise ValueError(f"no dimension {dim['name']} for {source_query}")
            return dimensions[dim["name"]]
    return "*"


def share_variables(texts, types):
    """Give every tank in a dataset the same variables so they can be written together.

    A variable a tank does not have is mapped to a mnemonic no subset contains, which
    bufr-query reads as all missing. Returns a list of problems.
    """
    problems = []
    tanks = list(texts)
    # The same query across tanks must have one name
    by_query = collections.defaultdict(list)
    for tank in tanks:
        for name, entry in _entries(texts[tank])[1].items():
            if "query" in entry["bufr"]:
                by_query[entry["bufr"]["query"]].append((tank, name))
    for members in by_query.values():
        canonical = _majority([name for _, name in members])
        for tank, name in members:
            if name != canonical and canonical not in _entries(texts[tank])[1]:
                texts[tank] = _rename_variable(texts[tank], name, canonical)

    # The same name with different units is two different things
    units = collections.defaultdict(list)
    for tank in tanks:
        for name, entry in _entries(texts[tank])[1].items():
            units[name].append((tank, entry["units"], entry["bufr"].get("query", "")))
    for name, members in units.items():
        keep = _majority([str(u) for _, u, _ in members])
        for tank, unit, query in members:
            if str(unit) != keep:
                suffix_text = re.sub(r"[^A-Za-z0-9]", "", query.split("/")[-1])
                texts[tank] = _rename_variable(texts[tank], name, f"{name}{suffix_text}")

    parsed = {tank: _entries(texts[tank]) for tank in tanks}
    union = {}
    for tank in tanks:
        for name, entry in parsed[tank][1].items():
            union.setdefault(name, (tank, entry))

    for tank in tanks:
        config, entries = parsed[tank]
        missing = [name for name in union if name not in entries]
        if not missing:
            continue
        bufr_lines, encoder_lines = [], []
        taken = {entry["key"] for entry in entries.values()}
        for name in missing:
            source_tank, entry = union[name]
            key = entry["key"]
            if key in taken:  # the same key can be in different groups across tanks
                key = name.replace("/", "_")
            taken.add(key)
            query = entry["bufr"].get("query")
            try:
                prefix = _absent_prefix(config, parsed[source_tank][0], query)
            except ValueError as error:
                problems.append(f"{tank}: {error}")
                continue
            absent = f"{prefix}/{ABSENT_MNEMONIC}"
            if query is None:
                fields = [f'        {field}: "{absent}"' for field in entry["bufr"]["datetime"]]
                bufr_lines += [f"    {key}:", "      datetime:", *fields, ""]
            else:
                kind = types[source_tank].get(re.sub(r"\{\d+\}", "", query[2:]), "float")
                bufr_lines += [f"    {key}:", f'      query: "{absent}"', f"      type: {kind}", ""]
            encoder_lines += [f'    - name: "{name}"', f"      source: variables/{key}",
                              f"      longName: {yaml_str(entry['long'])}"]  # fmt: skip
            if entry["units"]:
                encoder_lines.append(f'      units: "{entry["units"]}"')
            encoder_lines.append("")
        marker = "\n  splits:" if "\n  splits:" in texts[tank] else "\nencoder:"
        head, tail = texts[tank].split(marker, 1)
        comment = "    # Not in this tank: other tanks in this dataset have these"
        text = "\n".join([head.rstrip("\n"), "", comment, *bufr_lines]).rstrip("\n") + "\n" + marker + tail
        comment = "    # Not in this tank: read as missing so the dataset has one set of variables"
        texts[tank] = "\n".join([text.rstrip("\n"), "", comment, *encoder_lines]).rstrip("\n") + "\n"
    return problems


def main():
    queries_dir, tables_dir, geode_root, out_dir = sys.argv[1:5]
    wanted = sys.argv[5:]
    curated = read_curated(geode_root)
    mapping = read_table_a_mapping(geode_root)
    sizes_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bufr_tank_sequence_sizes.yaml")
    with open(sizes_path) as handle:
        sizes = yaml.safe_load(handle)
    os.makedirs(out_dir, exist_ok=True)
    summary, failures, texts, types = {}, {}, {}, {}
    datasets = collections.defaultdict(list)
    for path in sorted(glob.glob(f"{queries_dir}/b*.txt")):
        tank = os.path.basename(path)[:-4]
        profiles = MULTI_PROFILE_TANKS.get(tank, {None: None})
        for profile, sequence in profiles.items():
            key = f"{tank}_{profile}" if profile else tank
            try:
                subset, dim_paths, queries = parse_listing(path)
                others = [s for s in profiles.values() if s and s != sequence]
                queries = [q for q in queries if not any(q.path.startswith(f"{o}/") for o in others)]
                dim_paths = [p for p in dim_paths if not any(p[2:] == o or p[2:].startswith(f"{o}/") for o in others)]
                table_a, table_b = read_tables(f"{tables_dir}/{tank}.txt")
                replications = read_replications(f"{tables_dir}/{tank}.txt")
                text, info = build(
                    tank, subset, dim_paths, queries, table_a, table_b, curated, mapping, sizes,
                    replications, profile, sequence,
                )  # fmt: skip
            except ValueError as error:
                failures[key] = str(error)
                continue
            texts[key] = text
            types[key] = {q.path: q.dtype for q in queries}
            datasets[info["dataset"] or key].append(key)
            summary[key] = info

    problems = []
    for tanks in datasets.values():
        if len(tanks) > 1:
            group = {tank: texts[tank] for tank in tanks}
            problems += share_variables(group, types)
            texts.update(group)
    for tank, text in texts.items():
        yaml.safe_load(text)
        if not wanted or tank[:10] in wanted:
            with open(f"{out_dir}/{tank}.yaml", "w") as handle:
                handle.write(text)
    print(json.dumps({"generated": len(summary), "failures": failures, "problems": problems,
                      "unmapped": [t for t, i in summary.items() if not i["mapped"]],
                      "unknown_units": UNKNOWN_UNITS.most_common()}, indent=1))  # fmt: skip


if __name__ == "__main__":
    main()
