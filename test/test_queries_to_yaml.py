import yaml
from ush.queries_to_yaml import parse_queries, generate_yaml


def test_queries_to_yaml(tmp_path):
    """
    Test the parsing and YAML generation logic.
    """
    input_text = """
NC000101
 Dimensioning Sub-paths: 
  1d  *

 Queries: 
1d  int     NC000101/YEAR                   YEAR
1d  int     NC000101/MNTH                   MONTH
1d  int     NC000101/DAYS                   DAY
1d  int     NC000101/HOUR                   HOUR
1d  int     NC000101/MINU                   MINUTES
1d  float   NC000101/TMDB                   TEMPERATURE/DRY BULB TEMPERATURE
1d  int     NC000101/WMOB                   WMO BLOCK NUMBER
    """
    in_file = tmp_path / "query.txt"
    out_file = tmp_path / "output.yaml"

    in_file.write_text(input_text.strip())

    queries = parse_queries(str(in_file))
    assert len(queries) == 7
    assert queries[-1]["mnemonic"] == "WMOB"
    assert queries[-1]["query"] == "*/WMOB"

    generate_yaml(queries, str(out_file))

    # Read generated yaml and ensure structure
    with open(out_file, "r") as f:
        data = yaml.safe_load(f)

    assert "bufr" in data
    assert "encoder" in data

    bufr_vars = data["bufr"]["variables"]
    assert "timestamp" in bufr_vars
    assert "wmoBlockNumber" in bufr_vars
    assert "temperaturedryBulbTemperature" in bufr_vars

    enc_vars = data["encoder"]["variables"]
    names = [v["name"] for v in enc_vars]
    assert "MetaData/dateTime" in names
    assert "MetaData/wmoBlockNumber" in names
    assert "ObsValue/temperaturedryBulbTemperature" in names
