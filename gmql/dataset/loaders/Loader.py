from ...managers import get_python_manager, get_remote_manager, get_source_table
from ...settings import get_mode, get_gcloud_token
from ...FileManagment import TempFileManager
from ..parsers.RegionParser import RegionParser
from . import MetaLoaderFile, RegLoaderFile
import os
import gcsfs
from .MetadataProfiler import create_metadata_profile
from . import FILES_FOLDER, SCHEMA_FILE, WEB_PROFILE_FILE, PROFILE_FILE


def get_file_paths(path):
    real_path = preprocess_path(path)
    all_files = os.listdir(real_path)

    def filter_files(x):
        return not (x in [SCHEMA_FILE, WEB_PROFILE_FILE, PROFILE_FILE] or x.startswith("_"))

    files_paths = list(map(lambda x: os.path.join(real_path, x), filter(filter_files, all_files)))
    # files_paths = set(glob.glob(real_path + "/[!_]*"))
    schema_path = RegLoaderFile.get_schema_path(real_path)
    return files_paths, schema_path


def preprocess_path(path):
    """ Given a dataset path, the following structure is to be expected:
        - path/
            - files/
                - S_00000.gdm
                - S_00000.gdm.meta
                - S_00001.gdm
                - S_00001.gdm.meta
                - ...
                - schema.xml
                - [profile.xml]
                - [web_profile.xml]
            - [info.txt]
            - [query.txt]
            - [vocabulary.txt]

    :param path
    :return: the path where the gdm data are
    """
    if path.startswith("gs://"):
        fs = gcsfs.GCSFileSystem(token=get_gcloud_token())
        for sub_f in fs.ls(path):
            if sub_f.endswith("/") and sub_f.split("/")[-2] == FILES_FOLDER:
                return "gs://" + sub_f
        return path
    for sub_f in os.listdir(path):
        sub_f_tot = os.path.join(path, sub_f)
        if os.path.isdir(sub_f_tot) and sub_f == FILES_FOLDER:
            if check_for_dataset(sub_f_tot):
                return sub_f_tot
            else:
                raise ValueError("Dataset in {} was not in GMQL format".format(sub_f_tot))
    # if we are here it means that there is no files folder...so we need to check the root
    if check_for_dataset(path):
        return path
    else:
        raise ValueError("Dataset in {} was not in GMQL format".format(path))


def check_for_dataset(files):
    """ A GDM dataset has the form:
        - S_00000.gdm
        - S_00000.gdm.meta
        - S_00001.gdm
        - S_00001.gdm.meta
        - ...
        - schema.xml
        - [profile.xml]
        - [web_profile.xml]
    :param files: path of the dataset
    :return: True if the path contains a gdm dataset
    """
    all_files = os.listdir(files)
    meta_files = set(map(lambda y: y[: -9], filter(lambda x: x.endswith(".gdm.meta"), all_files)))
    regs_files = set(map(lambda y: y[: -4], filter(lambda x: x.endswith(".gdm"), all_files)))
    return meta_files == regs_files


def load_from_path(local_path=None, parser=None,  all_load=False):
    """ Loads the data from a local path into a GMQLDataset.
    The loading of the files is "lazy", which means that the files are loaded only when the
    user does a materialization (see :func:`~gmql.dataset.GMQLDataset.GMQLDataset.materialize` ).
    The user can force the materialization of the data (maybe for an initial data exploration on
    only the metadata) by setting the :attr:`~.reg_load` (load in memory the region data),
    :attr:`~.meta_load` (load in memory the metadata) or :attr:`~.all_load` (load both region and
    meta data in memory). If the user specifies this final parameter as True, a
    :class:`~gmql.dataset.GDataframe.GDataframe` is returned, otherwise a
    :class:`~gmql.dataset.GMQLDataset.GMQLDataset` is returned
    
    :param local_path: local path of the dataset
    :param parser: the parser to be used for reading the data
    :param all_load: if set to True, both region and meta data are loaded in memory and an 
                     instance of GDataframe is returned
    :return: A new GMQLDataset or a GDataframe
    """

    from .. import GDataframe
    from .. import GMQLDataset
    pmg = get_python_manager()

    local_path = preprocess_path(local_path)

    if all_load:
        # load directly the metadata for exploration
        meta = MetaLoaderFile.load_meta_from_path(local_path)
        if isinstance(parser, RegionParser):
            # region data
            regs = RegLoaderFile.load_reg_from_path(local_path, parser)
        else:
            regs = RegLoaderFile.load_reg_from_path(local_path)

        return GDataframe.GDataframe(regs=regs, meta=meta)
    else:
        from ...settings import is_metaprofiling_enabled
        if is_metaprofiling_enabled():
            meta_profile = create_metadata_profile(local_path)
        else:
            meta_profile = None

        if parser is None:
            # find the parser
            parser = RegLoaderFile.get_parser(local_path)
        elif not isinstance(parser, RegionParser):
            raise ValueError("parser must be RegionParser. {} was provided".format(type(parser)))

        source_table = get_source_table()
        id = source_table.search_source(local=local_path)
        if id is None:
            id = source_table.add_source(local=local_path, parser=parser)
        local_sources = [id]

        index = pmg.read_dataset(str(id), parser.get_gmql_parser())
        return GMQLDataset.GMQLDataset(index=index, parser=parser,
                                       location="local", path_or_name=local_path,
                                       local_sources=local_sources,
                                       meta_profile=meta_profile)


def load_from_remote(remote_name, owner=None):
    """ Loads the data from a remote repository.

    :param remote_name: The name of the dataset in the remote repository
    :param owner: (optional) The owner of the dataset. If nothing is provided, the current user
                  is used. For public datasets use 'public'.

    :return: A new GMQLDataset or a GDataframe
    """
    from .. import GMQLDataset
    pmg = get_python_manager()
    remote_manager = get_remote_manager()
    parser = remote_manager.get_dataset_schema(remote_name, owner)

    source_table = get_source_table()
    id = source_table.search_source(remote=remote_name)
    if id is None:
        id = source_table.add_source(remote=remote_name, parser=parser)
    index = pmg.read_dataset(str(id), parser.get_gmql_parser())
    remote_sources = [id]
    return GMQLDataset.GMQLDataset(index=index, location="remote", path_or_name=remote_name,
                                   remote_sources=remote_sources)


def load(path=None, name=None, owner=None, parser=None, all_load=False):
    # TODO: think if this method is useful or not...
    mode = get_mode()
    remote_manager = get_remote_manager()
    if mode == 'local':
        if isinstance(path, str) and (name is None):
            # we are given a local path
            return load_from_path(local_path=path, parser=parser, all_load=all_load)
        elif isinstance(name, str) and (path is None):
            local_path = TempFileManager.get_new_dataset_tmp_folder()
            remote_manager.download_dataset(dataset_name=name, local_path=local_path)
            return load_from_path(local_path=local_path, all_load=all_load)
        else:
            ValueError("You have to define path or name (mutually exclusive)")
    elif mode == 'remote':
        if isinstance(path, str) and (name is None):
            name = TempFileManager.get_unique_identifier()
            remote_manager.upload_dataset(dataset=path, dataset_name=name)
            return load_from_remote(remote_name=name)
        elif isinstance(name, str) and (path is None):
            return load_from_remote(remote_name=name, owner=owner)
        else:
            ValueError("You have to define path or name (mutually exclusive)")
    else:
        raise ValueError("Mode: {} unknown".format(mode))

