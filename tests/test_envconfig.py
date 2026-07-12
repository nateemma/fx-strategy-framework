from forex.core.env import EnvConfig

def test_defaults_when_empty_environ():
    e = EnvConfig.load(environ={})
    assert e.data_cache_dir == "data_cache" and e.dry_run is True and e.fred_api_key is None

def test_env_vars_override():
    e = EnvConfig.load(environ={"FRED_API_KEY": "abc", "FOREX_DATA_CACHE_DIR": "/tmp/c",
                                "FOREX_IB_PORT": "4002"})
    assert e.fred_api_key == "abc" and e.data_cache_dir == "/tmp/c" and e.ib_port == 4002

def test_env_overrides_file(tmp_path):
    p = tmp_path / "env.toml"
    p.write_text('data_cache_dir = "from_file"\noutput_dir = "of"\n')
    e = EnvConfig.load(path=p, environ={"FOREX_DATA_CACHE_DIR": "from_env"})
    assert e.data_cache_dir == "from_env"      # env beats file
    assert e.output_dir == "of"                # file value kept where no env
