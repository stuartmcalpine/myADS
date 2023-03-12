import os
import toml

# Working directory of ADS package (where database will be stored).
_wd = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# See if database folder exists, if not make it.
if not os.path.isdir(os.path.join(_wd, "database")):
    os.mkdir(os.path.join(_wd, "database"))

# Load the config file with users ADS info.
if not os.path.isfile(os.path.join(_wd, "myinfo.toml")):
    config = None
else:
    myinfo = toml.load(os.path.join(_wd, "myinfo.toml"))
    
    config = {
        "_DATABASE_FILE": os.path.join(_wd, "database", "mydatabase.toml"),
        "_FIRST_NAME": myinfo["info"]["first_name"],
        "_LAST_NAME": myinfo["info"]["last_name"],
        "_ADS_TOKEN": myinfo["info"]["ads_token"],
    }

    del myinfo
