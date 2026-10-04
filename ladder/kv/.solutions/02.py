db = {}
db["name"] = "Ada"
db["city"] = "London"


def put(key, value):
    db[key] = value


def get(key):
    return db[key]
