import pandas as pd
import numpy as np
import re

def cleanCSV(csv): #csv is the dataframe (pd.read_csv('file.csv'))
    d = csv.copy()
    d['Title'] = cleanTitle(d['Title'])
    d['Units'] = cleanUnits(d['Units'])
    d['Learning Activities'] = learnActivities(d['Description'])
    d['Grade Mode'] = gradeMode(d['Description'])
    d['General Education'] = genEd(d['Description'])
    return d

def cleanTitle(titles):
    rx = r"^—\u00A0([A-Za-z &:+,'-]+).*"
    titles = titles.str.extract(rx, expand=False).str.strip()
    return titles

def cleanUnits(units):
    rx0 = r"^\(([0-9]).*"
    units = units.str.extract(rx0, expand=False).astype(int)
    return units

def learnActivities(descriptions):
    rx2 = r"(?<=Learning Activities:)([^.]+)"
    act = descriptions.str.extract(rx2)
    return act

def gradeMode(descriptions):
    rx3 = r"(?<=Grade Mode:)([^.]+)"
    mode = descriptions.str.extract(rx3)
    mode[mode == 'P/NP only'] = 'Pass/No Pass only'
    return mode

def genEd(descriptions):
    rx4 = r"(?<=General Education:)([^.]+)"
    genEd = descriptions.str.extract(rx4)
    rx5 = r"(?<=\()[A-Z]+(?=\))"
    l = genEd[0].str.findall(rx5).str.join(', ')
    return l