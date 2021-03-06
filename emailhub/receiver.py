from redis_connector import redis_connector
import poplib
from email.parser import Parser
from email.header import decode_header
from email.utils import parseaddr
import time
import logging
import asyncio
from hashlib import md5


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(message)s",
                    datefmt = '[%Y-%m-%d  %H:%M:%S]'
                    )

class receiver():
    def __init__(self):
        self.connector = redis_connector()
        self.pop_server = "pop.163.com"
        self.abandon_list = []
        self.res_dict = {}
        self.epoch = 0
        

    def keep_listening(self, refresh_interval):
        while True:
            self.epoch += 1
            logging.info("epoch: {}, waiting for refresh...".format(self.epoch))
            time.sleep(refresh_interval)
            tasks = []
            loop = asyncio.get_event_loop()
            
            for member in self.connector.lcard(self.connector.mail_address_list):
                username = member.split("----")[0]
                password = member.split("----")[1]
                tasks.append(self.get_newest_mail(username, password))

            loop.run_until_complete(asyncio.wait(tasks))

            if self.res_dict:
                self.connector.client.hmset(self.connector.msg_queue_hash, self.res_dict)

            self.res_dict.clear()

            for member in self.abandon_list:
                self.connector.client.lrem(self.connector.mail_address_list, 1, member)
                self.connector.client.sadd(self.connector.abandon_list, member)

            
    async def get_newest_mail(self, username, password):
        server = poplib.POP3(self.pop_server)
        try:
            server.user(username)
            server.pass_(password)
        except Exception as e:
            logging.info("abandon user: {}".format(username))
            self.abandon_list.append("----".join([username, password]))
            return 

        stat = server.stat()
        if stat[0] == 0:
            return 

        resp, lines, octets = server.retr(stat[0])
        msg_content = []
        for line in lines:
            msg_content.append(bytes.decode(line))
        msg_content = "\r\n".join(msg_content)
        msg = Parser().parsestr(msg_content)
        
        res = []
        for part in msg.walk():
            if not part.is_multipart():
                data = part.get_payload(decode=True)
                charset = self.guess_charset(part)
                if charset:
                    data = data.decode(charset)
                    # title = msg["subject"].split("?")[3]
                    # title = title.encode("utf-8").decode(charset)
                if r"\u" in data:
                    data = data.encode('utf-8').decode('unicode_escape')
                res.append(data.strip())
                break
        server.close()
        res = "|".join(res) if res else None
        res_md5 = md5((username+res).encode("utf-8")).hexdigest()
        if res and not self.connector.client.sismember(self.connector.duplicate_set, res_md5):
            logging.info("user:{} receive a mail:\n".format(username)
                    +"- -"*12
                    + "\n{}\n".format(res) 
                    + "- -"*12)
            self.res_dict[username] = res
            self.connector.client.sadd(self.connector.duplicate_set, res_md5)


    def guess_charset(self, msg):
        charset = msg.get_charset()
        if charset is None:
            content_type = msg.get("content-type","").lower()
            pos = content_type.find("charset=")
            if pos >= 0:
                charset = content_type[pos + 8:].strip()
        return charset

