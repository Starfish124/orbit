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


def count():
    n = 0
    for key in db:
        n = n + 1
    return n


def find(value):
    keys = []
    for key, v in db.items():
        if v == value:
            keys.append(key)
    return sorted(keys)
