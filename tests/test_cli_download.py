import forex.cli as cli
import forex.data.refresh as refmod
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def test_run_download(monkeypatch):
    monkeypatch.setattr(refmod, "refresh_cache", lambda cache_dir, codes=None, loader=None: ["S1", "S2"])
    out = cli.run(RunConfig(universe=["AUD"]), EnvConfig(data_cache_dir="/tmp/x"), "download")
    assert out["download"]["series"] == ["S1", "S2"] and out["download"]["cache_dir"] == "/tmp/x"

def test_main_download_prints(monkeypatch, capsys):
    monkeypatch.setattr(refmod, "refresh_cache", lambda cache_dir, codes=None, loader=None: ["S1"])
    rc = cli.main(["download", "--universe", "AUD"])
    assert rc == 0 and "downloaded 1 series" in capsys.readouterr().out
