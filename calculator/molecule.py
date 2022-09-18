import os
import shutil

import numpy as np

from calculator.optimizer import Optimizer
from calculator.rbase import RMolecule
from common.constant import ElementInfo
from common.fio import JsonIO
from common.logger import logger


class Ligand(RMolecule):
    _LigandInfo = JsonIO.read("ligand.json")

    def __init__(self, name=None, smiles=None, rmol=None):
        super(Ligand, self).__init__(rmol)
        self.name = name
        self.smiles = smiles

    def __repr__(self):
        return f"<{self.__class__.__name__} : {self.name}>"

    @staticmethod
    def from_strings(symbol, name=None, addH=True):
        if name is None:
            name = symbol

        smiles = Ligand._LigandInfo[symbol]
        rmol = RMolecule.from_smiles(smiles, addH)

        return Ligand(name, smiles, rmol)

    def get_unsaturated_atoms(self):
        unsaturated_atoms = []
        for atom in self.atoms:
            if atom.is_unsaturated:
                unsaturated_atoms.append(atom)

        if len(unsaturated_atoms) > 1:
            logger.warning(f"Unsaturated atoms more than 1, may failed")
        elif not len(unsaturated_atoms):
            logger.warning(f"Unsaturated atoms equal to 0, may be a saturated molecule")

        return unsaturated_atoms


class MCenter(RMolecule):
    def __init__(self, name=None, rmol=None):
        super(MCenter, self).__init__(rmol)
        self.name = name

    @staticmethod
    def from_strings(symbol, name=None, addH=False):
        if name is None:
            name = symbol

        smiles = symbol
        if "[" not in symbol:
            smiles = f"[{symbol}]"

        rmol = RMolecule.from_smiles(smiles, addH)

        return MCenter(name, rmol)


class Molecule(object):
    def __init__(self, center, ligands, gfnff=True):
        self.center = center
        self.ligands = ligands
        self.optimized_position = None
        self.gfnff = gfnff

        self.rearrange()

    def __repr__(self):
        return f"{self.center}{self.ligands}"

    def rearrange(self):
        if len(self.ligands) == 2:
            matrix = np.array([(0, 1, 0), (0, -1, 0)])
        else:
            raise NotImplementedError(f"Number of ligands equal to {len(self.ligands)} is not supported now")

        default_bonds = ElementInfo[f'Element {self.center.name}']['default_bonds']
        ligand_atoms = [ligand.atoms for ligand in self.ligands]
        ligand_uatoms = [ligand.get_unsaturated_atoms() for ligand in self.ligands]

        # obtain the anchor atoms of each ligand_position
        anchor_atoms = [(uatom.symbol, uatom.position, uatom.order) for ligand in ligand_uatoms for uatom in ligand]
        if len(anchor_atoms) != len(self.ligands):
            raise RuntimeError(f"Anchor atoms num({len(anchor_atoms)}) is not equal ligands num({len(self.ligands)})")

        # calculate the delta vectors to the target position of the anchor atoms
        target_positions = []
        orders = []
        for anchor_atom, vector in zip(anchor_atoms, matrix):
            target_positions.append(default_bonds[f'Element {anchor_atom[0]}'] * vector)
            orders.append(anchor_atom[2])

        self.optimized_position = []
        for ligand_atom, target_position, order in zip(ligand_atoms, target_positions, orders):
            center_position = np.array(self.center.atoms[0].position)
            ligand_position = np.array([atom.position for atom in ligand_atom])
            ligand_symbol = [atom.symbol for atom in ligand_atom]
            optimizer = Optimizer(center=center_position, ligand=ligand_position)
            center_position, ligand_position = optimizer.optimize(target_position, order)
            for symbol, position in zip(ligand_symbol, ligand_position):
                self.optimized_position.append((symbol, position))
        self.optimized_position.append((self.center.atoms[0].symbol, center_position))

    def write_to_xyz(self, name="molecule.xyz"):
        with open("temp.xyz", "w") as f:
            f.write(f"{len(self.optimized_position)} \n")
            f.write(f"\n")
            for item in self.optimized_position:
                f.write(f"{item[0]}\t {'    '.join(item[1].astype(str))} \n")

        if self.gfnff:
            os.system(f"bash xtb.sh")
            shutil.move("xtbopt.xyz", name)
        else:
            shutil.move("temp.xyz", name)


if __name__ == '__main__':
    OAc = Ligand.from_strings("OAc")
    Pd = MCenter.from_strings("Rh")
    mol = Molecule(Pd, [OAc] * 2)
    mol.write_to_xyz()

    print()
