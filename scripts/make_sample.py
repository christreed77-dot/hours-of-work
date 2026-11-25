#!/usr/bin/env python3
"""Write site/data.json from SYNTHETIC data (flagged sample:true) so the site can be previewed offline."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import fake_fred, build_data as B
fake_fred.install()
data = B.build(sample=True)
out = os.path.join(os.path.dirname(__file__), "..", "site", "data.json")
json.dump(data, open(out, "w"), separators=(",", ":"))
print("wrote sample", out)
