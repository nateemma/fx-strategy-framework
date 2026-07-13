def split_params(params: dict, base_keys) -> tuple[dict, dict]:
    base = {k: params[k] for k in base_keys if k in params}
    rest = {k: v for k, v in params.items() if k not in base_keys}
    return base, rest

def split_prefixed(params: dict, prefixes) -> tuple[dict, dict]:
    inside = {k: v for k, v in params.items() if any(k.startswith(p + "_") for p in prefixes)}
    outside = {k: v for k, v in params.items() if k not in inside}
    return inside, outside

def build_components(specs, params: dict) -> dict:
    comps = {}
    for prefix, cls, defaults in specs:
        sub_p = dict(defaults)
        for k, v in params.items():
            if k.startswith(prefix + "_"):
                sub_p[k[len(prefix) + 1:]] = v
        comps[prefix] = cls(**sub_p)
    return comps
