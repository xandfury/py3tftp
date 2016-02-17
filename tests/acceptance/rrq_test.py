import unittest
import socket
import struct
import hashlib
from io import BytesIO
from os import remove as rm
from os.path import exists
from time import sleep


ACK = b'\x04\x00'
DAT = b'\x03\x00'


class TestRRQ(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('LICENSE', 'rb') as f:
            cls.license = f.read()
        cls.license_md5 = hashlib.md5(cls.license).hexdigest()
        cls.serverAddr = ('127.0.0.1', 8069,)
        cls.rrq = b'\x01\x00LICENSE\x00binary\x00'

    def setUp(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.counter = 1
        self.output = []
        self.data = None
        self.s.sendto(self.rrq, self.serverAddr)

    def tearDown(self):
        self.s.close()

    def test_perfect_scenario(self):
        while True:
            self.data, server = self.s.recvfrom(512)
            self.output += self.data

            msg = ACK + struct.pack('=H', self.counter)
            self.s.sendto(msg, server)
            self.counter += 1

            if len(self.data) < 512:
                break

        received = bytes(self.output)
        received_md5 = hashlib.md5(received).hexdigest()
        self.assertEqual(len(self.license), len(received))
        self.assertTrue(self.license_md5 == received_md5)

    def test_no_acks(self):
        no_ack = True
        while True:
            self.data, server = self.s.recvfrom(512)
            if self.counter % 5 == 0 and no_ack:
                # dont ack, discard data
                no_ack = False
            else:
                no_ack = True
                self.output += self.data

                msg = ACK + struct.pack('=H', self.counter)
                self.s.sendto(msg, server)
                self.counter += 1

                if len(self.data) < 512:
                    break

        received = bytes(self.output)
        received_md5 = hashlib.md5(received).hexdigest()
        self.assertEqual(len(self.license), len(received))
        self.assertTrue(self.license_md5 == received_md5)

    def test_total_timeout(self):
        # raises errno 111 in server - handle better
        max_msgs = 15
        while True:
            self.data, server = self.s.recvfrom(512)
            if self.counter >= max_msgs:
                break

            self.output += self.data
            msg = ACK + struct.pack('=H', self.counter)
            self.s.sendto(msg, server)
            self.counter += 1

            if len(self.data) < 512:
                break

        received = bytes(self.output)
        self.assertEqual((max_msgs - 1) * 512, len(received))


class TestWRQ(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.license_buf = BytesIO()
        with open('LICENSE', 'rb') as f:
            license = f.read()
            cls.license_buf.write(license)
            cls.license_buf.seek(0)
            cls.license_md5 = hashlib.md5(license).hexdigest()
        cls.serverAddr = ('127.0.0.1', 8069,)
        cls.wrq = b'\x02\x00LICENSE_TEST\x00binary\x00'

    def setUp(self):
        if exists('LICENSE_TEST'):
            rm('LICENSE_TEST')
        self.license = iter(lambda: self.license_buf.read(512), b'')
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.sendto(self.wrq, self.serverAddr)

    def tearDown(self):
        self.license_buf.seek(0)
        self.s.close()

    def test_perfect_transfer(self):
        for i, chunk in enumerate(self.license):
            ack, server = self.s.recvfrom(512)
            self.assertEqual(ack, ACK + struct.pack('=H', i))
            self.s.sendto(DAT + (i + 1).to_bytes(2,
                                                 byteorder='little') + chunk,
                          server)

        sleep(1)
        with open('LICENSE_TEST', 'rb') as f:
            license_test = f.read()
            license_test_md5 = hashlib.md5(license_test).hexdigest()

        self.assertEqual(len(license_test), self.license_buf.tell())
        self.assertEqual(self.license_md5, license_test_md5)

if __name__ == '__main__':
    unittest.main()
