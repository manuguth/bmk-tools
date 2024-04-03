from storages.backends.azure_storage import AzureStorage


class CustomAzureStorage(AzureStorage):
    def listdir(self, name):
        files = []
        dirs = []
        blob_list = self._client.list_blobs(name_starts_with=name)
        for blob in blob_list:
            files.append(blob.name[len(name) :])
        return dirs, files
