import os
import requests
import json
import time
from Bio.PDB import PDBParser, PDBIO, Select


def upload(path):
    """
    Uploads a PDB file to the ProteinsPlus web server

    Parameters
    ----------
    path: str
        Path to PDB file
    
    Returns
    -------
    pid: str
        ProteinsPlus ID
    """
    pp = requests.post("https://proteins.plus/api/pdb_files_rest", 
                       files={"pdb_file[pathvar]": open(path, "rb")})
    if pp.status_code == 400:
        raise ValueError("Bad request")
    loc = json.loads(pp.text)["location"]

    r = requests.get(loc)
    while r.status_code == 202:
        time.sleep(1)
        r = requests.get(loc)
    return json.loads(r.text)["id"]


def submit(pid):
    """
    Submits a PDB code to the Protoss web API

    Parameters
    ----------
    pid: str
        PDB code or ProteinsPlus ID
    
    Returns
    -------
    job: str
        URL of the Protoss job location
    """
    protoss = requests.post("https://proteins.plus/api/protoss_rest",
                            json={"protoss": {"pdbCode": pid}},
                            headers={"Accept": "application/json"})
    return json.loads(protoss.text)["location"]


def download(job, out, key="protein"):
    """
    Downloads a Protoss output file

    Parameters
    ----------
    job: str
        URL of the Protoss job location
    out: str
        Path to output file
    key: str
        Determines which file to download ("protein", "ligand", or "log")
    """
    r = requests.get(job)
    while r.status_code == 202:
        time.sleep(1)
        r = requests.get(job)

    protoss = requests.get(json.loads(r.text)[key])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        f.write(protoss.text)


def adjust_active_sites(path, metals): 
    """
    Deprotonates metal-coordinating residues that are (most likely) incorrectly 
    protonated by Protoss. Removes hydrogens from coordinating tyrosines and 
    cysteines, using a distance cutoff of 3 A.

    Parameters
    ----------
    path: str
        Path to existing Protoss output file, will be overwritten
    metals: list
        List of active site metal IDs
    """
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("PDB", path)

    points = []
    for res in structure[0].get_residues():
        if res.get_resname() in metals:
            points.append(res.get_unpacked_list()[0])

    class AtomSelect(Select):
        def accept_atom(self, atom):
            res = atom.get_parent()
            coord = None
            if atom.get_name() == "HH" and res.get_resname() == "TYR":
                coord = res["OH"]
            elif atom.get_name() == "HG" and res.get_resname() == "CYS":
                coord = res["SG"]
               
            if coord:
                for p in points:
                    if p - coord < 3:
                        return False
            return True

    io = PDBIO()
    io.set_structure(structure)
    io.save(path, AtomSelect())


def compute_charge(path):
    """
    Computes the total charge of each ligand

    Parameters
    ----------
    path: str
        Path to ligand SDF file
    
    Returns
    -------
    charge: dict
        Keyed by ligand ID
    """
    with open(path, "r") as f:
        sdf = f.read()
    ligands = [[t for t in s.splitlines() if t != ""] 
               for s in sdf.split("$$$$") if s != "\n" and s != ""]

    charge = {}
    for l in ligands:
        n = l[0].split("_")
        name = " ".join([f"{a}_{b}{c}" for a, b, c in zip(n[::3], n[1::3], n[2::3])])
        c = 0
        for line in l:
            if line.startswith("M  CHG"):
                c += sum([int(x) for x in line.split()[4::2]])
                break
        charge[name] = c
    return charge
