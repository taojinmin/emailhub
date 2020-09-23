import redis


class redis_connector():
    def __init__(self):
        self._init_client()
        self.mail_address_list = "mail_address"
        self.msg_queue_hash = "msg_queue_hash"
        self.abandon_list = "abandon_list"
        self.duplicate_set = "duplicate_set"


    def _init_client(self):
        self.client = redis.StrictRedis(host="localhost", port=6379,decode_responses=True)


    def upload_mail_address(self):
        with open("./mail_address.txt") as f:
            for line in f.readlines():
                self.client.rpush(self.mail_address_list, line.strip())


    def lcard(self, name):
        list_count = self.client.llen(name)
        for index in range(list_count):
            yield self.client.lindex(name, index)


if __name__ == "__main__":
    connector = redis_connector()
    connector.upload_mail_address()
