import logging
import os
from typing import (
    Text,
    Optional,
    Type,
    Union
)

from paramiko import SFTPAttributes
from typeguard import typechecked
from sshmitm.exceptions import MissingClient

from sshmitm.forwarders.sftp import SFTPHandlerPlugin, SFTPBaseHandle
from sshmitm.interfaces.sftp import SFTPProxyServerInterface, BaseSFTPServerInterface


class SFTPProxyReplaceHandler(SFTPHandlerPlugin):
    """Replaces a SFTP transmitted File during transit
    """

    class SFTPInterface(SFTPProxyServerInterface):

        @typechecked
        def lstat(self, path: Text) -> Union[SFTPAttributes, int]:
            self.session.sftp_client_ready.wait()
            args, _ = SFTPProxyReplaceHandler.parser().parse_known_args()
            if self.session.sftp_client is None:
                raise MissingClient("self.session.sftp_client is None!")
            stat_remote = self.session.sftp_client.lstat(path)
            if isinstance(stat_remote, int):
                return stat_remote
            stat_replace = SFTPAttributes.from_stat(os.stat(args.sftp_replacement_file))
            stat_remote.st_size = stat_replace.st_size
            return stat_remote

        @typechecked
        def stat(self, path: Text) -> Union[SFTPAttributes, int]:
            return self.lstat(path)

    @classmethod
    @typechecked
    def get_interface(cls) -> Optional[Type[BaseSFTPServerInterface]]:
        return cls.SFTPInterface

    @classmethod
    def parser_arguments(cls) -> None:
        plugin_group = cls.parser().add_argument_group(cls.__name__)
        with open('/tmp/sftp_file', 'w') as f:
            f.write('Manish_sftp_file_is_replaced')

    def __init__(self, sftp: SFTPBaseHandle, filename: Text) -> None:
        super().__init__(sftp, filename)
        self.args.sftp_replacement_file = '/tmp/sftp_file'

        logging.info("intercepting sftp file '%s', replacement: %s", filename, self.args.sftp_replacement_file)
        self.replacement = open(self.args.sftp_replacement_file, "rb")
        self.file_uploaded = False
        self.data_handled = False

    def close(self) -> None:
        self.replacement.close()

    @typechecked
    def handle_data(self, data: bytes, *, offset: Optional[int] = None, length: Optional[int] = None) -> bytes:
        self.data_handled = True
        if self.file_uploaded:
            return b''
        if self.sftp.writefile:
            self.file_uploaded = True
            return self.replacement.read()
        if length is not None:
            return self.replacement.read(length)
        return b''
