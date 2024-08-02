import os
import shutil
from datetime import timedelta, datetime

import fitz

from path import get_work_path


def recover_pix(doc, item):
    xref = item[0]  # xref of PDF image
    smask = item[1]  # xref of its /SMask

    # special case: /SMask or /Mask exists
    if smask > 0:
        pix0 = fitz.Pixmap(doc.extract_image(xref)["image"])
        if pix0.alpha:  # catch irregular situation
            pix0 = fitz.Pixmap(pix0, 0)  # remove alpha channel
        mask = fitz.Pixmap(doc.extract_image(smask)["image"])

        try:
            pix = fitz.Pixmap(pix0, mask)
        except:  # fallback to original base image in case of problems
            pix = fitz.Pixmap(doc.extract_image(xref)["image"])

        if pix0.n > 3:
            ext = "pam"
        else:
            ext = "png"

        return {  # create dictionary expected by caller
            "ext": ext,
            "colorspace": pix.colorspace.n,
            "image": pix.tobytes(ext),
        }

    # special case: /ColorSpace definition exists
    # to be sure, we convert these cases to RGB PNG images
    if "/ColorSpace" in doc.xref_object(xref, compressed=True):
        pix = fitz.Pixmap(doc, xref)
        pix = fitz.Pixmap(fitz.csRGB, pix)
        return {  # create dictionary expected by caller
            "ext": "png",
            "colorspace": 3,
            "image": pix.tobytes("png"),
        }
    return doc.extract_image(xref)


def get_image(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)

    page_count = doc.page_count  # number of pages

    xref_list = []
    first_image = ""
    for pno in range(page_count):
        il = doc.get_page_images(pno)
        for img in il:
            xref = img[0]
            if xref in xref_list:
                continue
            # width = img[2]
            # height = img[3]
            # if min(width, height) <= 100:
            #     continue
            image = recover_pix(doc, img)
            n = image["colorspace"]
            imgdata = image["image"]

            # if len(imgdata) <= 2048:
            #     continue
            # if len(imgdata) / (width * height * n) <= 0.05:
            #     continue

            img_file = os.path.join(os.path.dirname(pdf_path), f"page_{pno}_img_{xref}.{image['ext']}")
            with open(img_file, "wb") as fout:
                fout.write(imgdata)

            if first_image == "":
                first_image = os.path.relpath(img_file, os.path.join(get_work_path(), 'output'))

            xref_list.append(xref)

    return first_image


def compress_folder():
    output_path = get_work_path()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    shutil.make_archive(
        f'{yesterday}-summary',
        'zip',
        output_path,
        'output'
    )
