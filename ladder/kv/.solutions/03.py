db = {}
db["name"] = "Ada"
db["city"] = "London"


def put(key, value):
    db[key] = value


def get(key):
    if key not in db:
        return None
    return db[key]


def delete(key):
    if key not in db:
        return False
    del db[key]
    return True
