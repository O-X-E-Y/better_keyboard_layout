from os import cpu_count
from os.path import getsize
from glob import glob
import concurrent.futures
from time import perf_counter


def time_this(func):
    def wrapper(*args, **kwargs):
        start = perf_counter()
        result = func(*args, **kwargs)
        end = perf_counter()
        print(f"\"{func.__name__}\" took {round(end - start, ndigits=6 if end-start < 0.1 else 3)} second(s)\n")
        return result

    return wrapper


def _utf_to_ascii_table():
    utf_stuff =  "\t\n \"+:<>?ABCDEFGHIJKLMNOPQRSTUVWXYZ\\_{|}~«´»ÀÁÂÄÇÈÉÊËÌÍÎÏÐÑÒÓÔÖÙÚÛÜÝàáâäçèéêëìíîïðñòóôö÷øùúûüý‘“”’–ʹ͵"
    translation = "   \'=;,./abcdefghijklmnopqrstuvwxyz\\-[\\]`'''aaaaceeeeiiiidnoooouuuuyaaaaceeeeiiiidnoooo/ouuuuy''''-''"
    exceptions = utf_stuff + translation
    replace = ''.join([chr(c) for c in range(0, int("110000", 16)) if chr(c) not in exceptions])
    return str.maketrans(utf_stuff, translation, replace)


sanitization_table = _utf_to_ascii_table()


def _chunk_length(piece: tuple[str, list[int, int]]):
    """
    Given a tuple containing a string and a list containing
    chunk count and the length, gives the length of the chunk
    :param piece: the tuple
    :return: the length of the path's content
    """
    return piece[1][1]


def _all_small_chunks(chunk_info: list[list[int, int]]):
    for info in chunk_info:
        if info[1] > 2_000_000:
            return False
    return True


def _has_max_chunks(chunk_info: list[list[int, int]], cpus):
    for info in chunk_info:
        if info[0] >= cpus:
            return True
    return False


def create_chunks(language: str, text_directory: str):
    """
    Generates a more optimal distribution of work to analyse.
    Creates the framework to chunk big texts up into smaller parts, if applicable.
    :param language: the language to use when looking for text files.
    :param text_directory: the directory the files should be in.
    :return: a list of tuples, which contain the path to the text and the amount pieces it should be chunk into.
    """
    paths = glob(f"corpus_analysis/{text_directory}/{language}/*.txt")
    if len(paths) == 0:
        return None
    chunk_info = {path: [1, getsize(path)] for path in paths}
    cpus = cpu_count()
    values = chunk_info.values()

    while not _all_small_chunks(values) and not _has_max_chunks(values, cpus):
        chunk_info = sorted(chunk_info.items(), key=_chunk_length, reverse=True)

        chunk_info[0][1][1] *= chunk_info[0][1][0] / (chunk_info[0][1][0] + 1)
        chunk_info[0][1][0] += 1

        chunk_info = dict(chunk_info)
        values = chunk_info.values()

    return [(path, info[0]) for path, info in chunk_info.items()]


def open_text(chunk: (str, int)):
    with open(chunk[0], 'r', encoding='utf-8') as file:
        return file.read(), chunk[1]


def chunk_text(text_chunk: (str, int)):
    text, chunk_count = text_chunk
    text = text.translate(sanitization_table)
    width = len(text)
    if chunk_count == 1:
        return [text]
    size = width // chunk_count + 1
    return [text[i*size: (i+1)*size] for i in range(chunk_count)]


def chunk_texts(language: str, text_directory: str):
    chunks = create_chunks(language, text_directory)
    if len(chunks) >= 1:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            text_chunks = executor.map(open_text, chunks)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            return sum(list(executor.map(chunk_text, text_chunks)), [])
    else:
        print("There are no files in that directory")
        return
