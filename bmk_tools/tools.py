from storages.backends.azure_storage import AzureStorage


class CustomAzureStorage(AzureStorage):
    """
    A custom implementation of AzureStorage class.

    This class extends the AzureStorage class and provides additional functionality for listing directories and files.

    Parameters:
    ----------
    AzureStorage : class
        The base class for Azure Storage.

    Attributes:
    ----------
    _client : object
        The client object for interacting with Azure Storage.

    Methods:
    -------
    listdir(name):
        Lists the directories and files in the specified directory.

    """

    def listdir(self, name):
        """
        Lists the directories and files in the specified directory.

        Parameters:
        ----------
        name : str
            The name of the directory.

        Returns:
        -------
        dirs : list
            A list of directories in the specified directory.

        files : list
            A list of files in the specified directory.

        """
        files = []
        dirs = []
        # blob_list = self._client.list_blobs(name_starts_with=name)
        blob_list = self.connection.list_blobs(
            self.azure_container, name_starts_with=name
        )
        for blob in blob_list:
            files.append(blob.name[len(name) :])
        return dirs, files
