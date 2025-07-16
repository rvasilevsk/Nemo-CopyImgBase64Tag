import base64
import json
import os
import sys
import tkinter as tk
from dataclasses import asdict, dataclass
from html import escape
from io import BytesIO, StringIO
from pathlib import Path

import pyperclip

# TODO:
# ~ $HOME
# mime by file content
# skip unsupported mimes
# chunked base64
# ru
# kb, mb
# alt format

CHUNK_SIZE = 120
MAX_FILE_SIZE = 10_000_000
ALT_FORMAT = "$name"


##############################################################################
# Conf
##############################################################################
def int_not_negative(n, default):
    try:
        n = int(n)
    except ValueError:
        return default
    if n < 0:
        return default
    return n


def int_positive(n, default):
    try:
        n = int(n)
    except ValueError:
        return default
    if n < 1:
        return default
    return n


@dataclass
class Conf:
    chunk_size: int
    max_file_size: int
    alt_format: str


def conf_path():
    return Path(__file__).with_suffix(".json")


def conf_default():
    return Conf(CHUNK_SIZE, MAX_FILE_SIZE, ALT_FORMAT)


def conf_create_default():
    path = conf_path()
    conf = conf_default()
    f = open(path, "w", encoding="utf-8")
    json.dump(asdict(conf), f, indent=4)


# conf_create_default()


def conf_from_dict(d):
    conf = conf_default()
    dd = {}
    sz = d.get("chunk_size", conf.chunk_size)
    sz = int_not_negative(sz, conf.chunk_size)
    dd["chunk_size"] = sz

    sz = d.get("max_file_size", conf.max_file_size)
    sz = int_positive(sz, conf.max_file_size)
    dd["max_file_size"] = sz

    dd["alt_format"] = d.get("alt_format", conf.alt_format)
    return Conf(**dd)


def read_conf():
    path = conf_path()
    print(conf_path)
    try:
        f = open(path, encoding="utf-8")
    except Exception:
        return conf_default()

    data = json.load(f)
    return conf_from_dict(data)


##############################################################################
# Tk
##############################################################################
def tk_root():
    root = tk.Tk()
    root.bind("<Escape>", lambda x: root.destroy())
    root.bind("<Control-q>", lambda x: root.destroy())
    return root


def displayError(error):
    root = tk_root()
    root.title("Error")
    root.geometry("400x100")
    label = tk.Label(root, text=error)
    label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    root.mainloop()


def displayMgs(title, msg):
    root = tk_root()
    root.title(title)
    root.geometry("800x600")
    label = tk.Label(root, text=msg)
    label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    root.mainloop()


##############################################################################
# file stuff
##############################################################################
def unexpand_user(path: str | Path) -> str | Path:
    s = str(path)
    home = os.path.expanduser('~')
    if not s.startswith(home):
        return path
    s = s.replace(home, '~', 1)
    return Path(s) if isinstance(path, Path) else s


class FileTooLargeError(OSError):
    def __init__(self, strerror, filename, filesize, maxsize):
        super().__init__(-1, strerror, filename)
        self.filesize = filesize
        self.maxsize = maxsize


def open_max_size(file: Path, mode, max_size, **kwargs):
    file = file.expanduser()
    sz = os.stat(file).st_size
    if sz > max_size:
        s = f"file size ({sz}) greate than max_file_size ({max_size})"
        raise FileTooLargeError(s, file, sz, max_size)
    return open(file, mode, **kwargs)


##############################################################################
# ImgTag
##############################################################################
def mime_by_path(path: Path) -> bytes:
    ext = path.suffix[1:].lower()
    d = dict(
        jpeg=b"image/jpeg",
        jpg=b"image/jpeg",
        gif=b"image/gif",
        webp=b"image/webp",
        tga=b"image/x-tga",
        tpic=b"image/x-tga",
        vda=b"image/x-tga",
        vst=b"image/x-tga",
        icb=b"image/x-tga",
    )
    return d.get(ext, b"image/png")


class ImgTag:
    def __init__(self, filepath, conf):
        self.filepath = Path(filepath)
        self.out = BytesIO()
        self.conf = conf

    def __repr__(self):
        sz = self.out.getbuffer().nbytes
        name = self.filepath.name
        # s1 = self.out[:32]
        return f"<ImgTag name={name} size={sz}>"

    def mime_by_path(self):
        return mime_by_path(self.filepath)

    def write(self, data: bytes):
        self.out.write(data)

    def write_ln_chunked(self, data: bytes, sz=120):
        l = len(data)
        n = 0
        m = n + sz
        while n < l:
            self.out.write(b"\n")
            self.out.write(data[n:m])
            n = m
            m += sz

    def sp(self):
        self.out.write(b" ")

    def ln(self):
        self.out.write(b"\n")

    def tag(self):
        self.out.write(b"<img ")

    def tag_close(self):
        self.out.write(b">")

    def alt(self):
        s = self.filepath.name
        b = escape(s).encode("utf-8")
        self.out.write(b'alt="')
        self.out.write(b)
        self.out.write(b'"')

    def b64(self):
        f = open_max_size(self.filepath, "rb", self.conf.max_file_size)
        b = f.read()
        b = base64.b64encode(b)
        if self.conf.chunk_size:
            self.write_ln_chunked(b, self.conf.chunk_size)
        else:
            self.out.write(b)

    # def _b64_chunked(self):
    #     sz = 80
    #     with open(self.filepath, "rb") as f:
    #         b = f.read(sz)
    #         while b:
    #             self.out.write("\n")
    #             b = base64.b64encode(b)
    #             self.out.write(b)
    #             b = f.read(sz)

    def mime_b64(self):
        mime = self.mime_by_path()
        self.out.write(b"data:")
        self.out.write(mime)
        self.out.write(b";base64,")
        self.b64()

    def src(self):
        self.out.write(b'src="')
        self.mime_b64()
        self.out.write(b'"')

    def all(self):
        self.tag()
        self.alt()
        self.sp()
        self.src()
        self.tag_close()
        self.ln()

    def val_bytes(self):
        return self.out.getvalue()

    def val_str(self):
        return self.out.getvalue().decode("utf-8")

    def copy(self):
        pyperclip.copy(self.val_str())


##############################################################################
# ImgTagMulty
##############################################################################
class ImgTagMulty:
    def __init__(self, files, conf):
        self.files = files
        self.conf = conf
        self.tags = []
        self.errs = []

    def run(self):
        for f in self.files:
            try:
                t = ImgTag(f, self.conf)
                t.all()
                self.tags.append(t)
            except OSError as e:
                self.errs.append(e)

    def ntags(self):
        return len(self.tags)

    def nerrs(self):
        return len(self.errs)

    def res_lines_gen(self):
        n = self.ntags()
        if n:
            yield f"Done ({n}):"
            yield from (repr(t) for t in self.tags)

        n = self.nerrs()
        if n:
            yield f"Errors ({n}):"
            yield from (f"{unexpand_user(e.filename)}: {e.strerror}" for e in self.errs)

    def res_lines(self):
        return list(self.res_lines_gen())

    def res_text(self):
        return "\n".join(self.res_lines_gen())

    def val_bytes(self):
        out = BytesIO()
        for t in self.tags:
            out.write(t.val_bytes())
        return out.getvalue()

    def val_str(self):
        out = StringIO()
        for t in self.tags:
            out.write(t.val_str())
        return out.getvalue()

    def copy(self):
        pyperclip.copy(self.val_str())


##############################################################################
# start
##############################################################################
def main(files):
    if not files:
        displayError("Empty file list")
        return

    cfg = read_conf()
    # print(asdict(cfg))
    t = ImgTagMulty(files, cfg)
    t.run()
    t.copy()
    # print(t.res_text())
    displayMgs("hello", t.res_text())


if __name__ == "__main__":
    files = sys.argv[1:]
    files = [
        "~/Pictures/dos_not_exists.jpg",
        "~/Pictures/antarktida_small.jpg",
        "~/Pictures/antarktida_small.tga",
        "~/Pictures/antarktida_small.webp",
        "~/Pictures/grunt.gif",
        "~/Pictures/simplenote.png",
        "~/Pictures/photos1.iso",
    ]
    main(files)
