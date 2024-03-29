# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from botbuilder.schema import Attachment


class UserProfile:
    """
      This is our application state. Just a regular serializable Python class.
    """

    def __init__(self, name: str = None, podcast: str = None, query: str = None):
        self.name = name
        self.podcast = podcast
        self.query = query
