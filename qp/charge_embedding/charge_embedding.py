"""Generate charge embedding ptchrges.xyz file for TeraChem input."""

import os
import shutil
import numpy as np

def rename_and_clean_resnames(input_pdb, output_pdb):
    """
    Changes the names of protoss-generated resnames from HIS to HIP, HIE, or HID.
    Similiar rules with OXT also renames HETATM to ATOM.
    HETATMs in QM region will get removed anyway.

    Notes
    -----
    Current issues: need to deal with spacing issues down the line caused by creating a four letter residue name

    """
    with open(input_pdb, 'r') as infile, open(output_pdb, 'w') as outfile:
        lines = infile.readlines()

        # Identify residues to rename based on the specified conditions
        residue_info = {}
        for line in lines:
            if line.startswith('ATOM') or line.startswith('HETATM'):
                atom_name = line[12:16].strip()
                residue_name = line[17:20].strip()
                chain_id = line[21].strip()
                residue_id = line[22:26].strip()
                key = (residue_name, chain_id, residue_id)

                if key not in residue_info:
                    residue_info[key] = {
                        'residue_name': residue_name,
                        'atoms': set()
                    }
                residue_info[key]['atoms'].add(atom_name)

        # Determine the new residue names based on the conditions
        for key, info in residue_info.items():
            atoms = info['atoms']
            if info['residue_name'] == 'HIS':
                if 'HD1' in atoms and 'HE2' in atoms:
                    info['new_name'] = 'HIP'
                elif 'HD1' in atoms and 'HE2' not in atoms:
                    info['new_name'] = 'HID'
                elif 'HE2' in atoms and 'HD1' not in atoms:
                    info['new_name'] = 'HIE'
                else:
                    info['new_name'] = info['residue_name']
            else:
                info['new_name'] = info['residue_name']

            if 'OXT' in atoms:
                info['new_name'] = 'C' + info['new_name']

            if {'N', 'H1', 'H2', 'H3'} <= atoms:
                info['new_name'] = 'N' + info['new_name']

        # Write the modified PDB file with the new residue names
        for line in lines:
            if line.startswith('ATOM') or line.startswith('HETATM'):
                residue_name = line[17:20].strip()
                chain_id = line[21].strip()
                residue_id = line[22:26].strip()
                key = (residue_name, chain_id, residue_id)
                if key in residue_info:
                    new_residue_name = residue_info[key]['new_name']
                    line = line[:17] + f"{new_residue_name:>3}" + line[20:]
                if line.startswith('HETATM'):
                    line = 'ATOM  ' + line[6:]
            outfile.write(line)

def read_ff_dict(dict_file):
    ff_dict = {}
    with open(dict_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            residue_name = parts[0]
            atom_name = parts[1]
            charge_value = float(parts[2])
            ff_dict.setdefault(residue_name, {})[atom_name] = charge_value
    return ff_dict

def parse_pdb(input_pdb, output_pdb, ff_dict):
    with open(input_pdb, 'r') as infile, open(output_pdb, 'w') as outfile:
        for line in infile:
            if line.startswith('ATOM'):
                atom_name = line[12:16].strip()
                residue_name = line[17:20].strip()
                if atom_name in ff_dict.get(residue_name, {}):
                    # Dump information into the B-factor column (columns 61-66)
                    ff_value = ff_dict[residue_name][atom_name]
                    line = line[:60] + f"{ff_value:>6.2f}" + line[66:]
                    outfile.write(line)

def read_pdb(file_path):
    """
    Read a PDB file and extract atom lines.
    """
    atom_lines = []
    with open(file_path, 'r') as pdb_file:
        for line in pdb_file:
            if line.startswith('ATOM'):
                atom_lines.append(line)
    return atom_lines

def read_xyz(file_path):
    """
    Read an XYZ file and extract atom coordinates.
    """
    coordinates = []
    with open(file_path, 'r') as xyz_file:
        for line in xyz_file:
            parts = line.split()
            if len(parts) == 4:
                x = float(parts[1])
                y = float(parts[2])
                z = float(parts[3])
                coordinates.append([x, y, z])
    return np.array(coordinates)

def remove_atoms_from_pdb(pdb_lines, xyz_coords, threshold):
    """
    Remove atoms from the PDB file whose coordinates are within the threshold distance of any XYZ coordinates.
    """
    new_pdb_lines = []
    for line in pdb_lines:
        if line.startswith('ATOM'):
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
            pdb_coord = np.array([x, y, z])
            min_distance = min(np.linalg.norm(pdb_coord - xyz_coord) for xyz_coord in xyz_coords)
            if min_distance > threshold:
                new_pdb_lines.append(line)
        else:
            new_pdb_lines.append(line)
    return new_pdb_lines

def write_pdb(output_path, pdb_lines):
    """
    Write the remaining atoms to a new PDB file.
    """
    with open(output_path, 'w') as pdb_file:
        for line in pdb_lines:
            pdb_file.write(line)

def remove_qm_atoms(pdb_file, xyz_file, output_pdb_file, threshold=0.5):

    pdb_lines = read_pdb(pdb_file)
    xyz_coords = read_xyz(xyz_file)

    remaining_lines = remove_atoms_from_pdb(pdb_lines, xyz_coords, threshold)

    write_pdb(output_pdb_file, remaining_lines)

def parse_pdb_to_xyz(pdb_file_path, output_file_path):
    """
    Write terachem file test
    """
    with open(pdb_file_path, 'r') as pdb_file:
        lines = pdb_file.readlines()

    atom_count = 0
    with open(output_file_path, 'w') as output_file:
        for line in lines:
            if line.startswith('ATOM'):
                atom_count += 1

        output_file.write(str(atom_count) + '\n')
        output_file.write('Generated from PDB file\n')  # XYZ format allows a comment line

        for line in lines:
            if line.startswith('ATOM'):
                charges = float(line[60:66])
                x_coord = float(line[30:38])
                y_coord = float(line[38:46])
                z_coord = float(line[46:54])
                output_file.write(f"{charges} {x_coord} {y_coord} {z_coord}\n")

if __name__ == "__main__":
    # Setup a temporary directory to store files
    temporary_files_dir = "ptchrges_temp"
    os.mkdir(temporary_files_dir)

    pdb_name = os.getcwd().split('/')[-3]
    protoss_pdb_name = f'{pdb_name}_protoss.pdb'
    protoss_pdb_path = os.path.join("/".join(os.getcwd().split('/')[:-2]),"Protoss",protoss_pdb_name)
    chain_name = os.getcwd().split('/')[-2]
    renamed_his_pdb_file = f'{temporary_files_dir}/{chain_name}_rename_his.pdb'
    dict_file = 'ff14SB.dict' # residue names, atom names, and charge values
    charges_pdb = f'{temporary_files_dir}/{chain_name}_added_charges.pdb'
    xyz_file = f'{chain_name}.xyz'
    pdb_no_qm_atoms = f'{temporary_files_dir}/{chain_name}_without_qm_atoms.pdb'
    final_point_charges_file = "ptchrges.xyz"

    # Rename histidines
    rename_and_clean_resnames(protoss_pdb_path, renamed_his_pdb_file)
    # Read the dictionary file into a dictionary
    ff_dict = read_ff_dict(dict_file)
    # Parse the PDB file and dump charge information into the B-factor column
    parse_pdb(renamed_his_pdb_file, charges_pdb, ff_dict)
    # Remove QM atoms
    remove_qm_atoms(charges_pdb, xyz_file, pdb_no_qm_atoms, threshold=0.5)
    parse_pdb_to_xyz(pdb_no_qm_atoms, final_point_charges_file)


    shutil.rmtree(temporary_files_dir)
