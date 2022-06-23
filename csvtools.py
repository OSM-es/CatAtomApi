"""CSV related help functions."""
import csv
import io
import os

delimiter="\t"


def dict2csv(csv_path, a_dict):
    """
    Write a dictionary to a csv file.

    Optinally sorted by key (sort=0) or value (sort=1)
    """
    with open(csv_path, "w") as csv_file:
        dictitems = list(a_dict.items())
        for (k, v) in dictitems:
            csv_file.write("%s%s%s%s" % (k, delimiter, delimiter.join(v), "\n"))


def csv2dict(csv_path, a_dict=None):
    """Read a dictionary from a csv file."""
    a_dict = {} if a_dict is None else a_dict
    if os.path.exists(csv_path):
        with open(csv_path) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=str(delimiter))
            for row in csv_reader:
                a_dict[row[0]] = row[1:]
    return a_dict
