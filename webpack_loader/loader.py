import json
import time
import logging

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage

from .exceptions import WebpackError, WebpackLoaderBadStatsError
from .config import load_config

logger = logging.getLogger('webpack_loader')


class WebpackLoader(object):
    _assets = {}

    def __init__(self, name='DEFAULT'):
        self.name = name
        self.config = load_config(self.name)

    def _load_assets(self):
        try:
            with open(self.config['STATS_FILE']) as f:
                return json.load(f)
        except IOError:
            raise IOError(
                'Error reading {0}. Are you sure webpack has generated '
                'the file and the path is correct?'.format(
                    self.config['STATS_FILE']))

    def get_assets(self):
        if self.config['CACHE']:
            if self.name not in self._assets:
                self._assets[self.name] = self._load_assets()
            return self._assets[self.name]
        return self._load_assets()

    def filter_chunks(self, chunks):
        for chunk in chunks:
            ignore = any(regex.match(chunk['name'])
                         for regex in self.config['ignores'])
            if not ignore:
                chunk['url'] = self.get_chunk_url(chunk)
                yield chunk

    def get_chunk_url(self, chunk):
        public_path = chunk.get('publicPath')
        if public_path:
            return public_path

        relpath = '{0}{1}'.format(
            self.config['BUNDLE_DIR_NAME'], chunk['name']
        )
        return staticfiles_storage.url(relpath)

    def get_bundle(self, bundle_name):
        assets = self.get_assets()
        logger.debug("[{}][{}] get_bundle".format(
            bundle_name,  assets.get('status')))

        if settings.DEBUG:
            if assets['status'] == 'compiling':
                if 'file' not in assets:
                    assets['file'] = ''

                error = u"{file} is compiling ".format(**assets)
                logger.error("[{}][ERROR] {}".format(
                    bundle_name,  error))
                raise IOError(error)

        if assets.get('status') == 'done':
            chunks = assets['chunks'][bundle_name]
            return self.filter_chunks(chunks)

        elif assets.get('status') == 'error':
            if 'file' not in assets:
                assets['file'] = ''
            error = u"""
            {error} in {file}
            {message}
            """.format(**assets)
            raise WebpackError(error)

        raise WebpackLoaderBadStatsError(
            "The stats file does not contain valid data. Make sure "
            "webpack-bundle-tracker plugin is enabled and try to run "
            "webpack again.")
