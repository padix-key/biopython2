# This source code is part of the Biotite package and is distributed
# under the 3-Clause BSD License. Please see 'LICENSE.rst' for further
# information.

import pytest
import json
import numpy as np
import biotite.structure as struc
import biotite.structure.io as strucio
from biotite.structure.info import residue
from biotite.structure.residues import get_residue_masks
from biotite.structure.hbond import hbond
from os.path import join
from ..util import data_dir
# For ``base_pairs_edge`` differences to a reference can be arbitrary as
# the number hydrogen bonds between two different edges can be equal. In
# order to distinguish arbitrarily identified edges from wrongfully
# identified edges the full edge matrix, listing the number of hydrogen
# bonds for each edge has to be considered.
from biotite.structure.basepairs import _get_edge_matrix


def reversed_iterator(iter):
    """
    Returns a reversed list of the elements of an Iterator.
    """
    return reversed(list(iter))


@pytest.fixture
def nuc_sample_array():
    return strucio.load_structure(join(data_dir("structure"), "1qxb.cif"))


@pytest.fixture
def basepairs(nuc_sample_array):
    """
    Generate a test output for the base_pairs function.
    """
    residue_indices, residue_names = struc.residues.get_residues(
        nuc_sample_array
    )[0:24]
    return np.vstack((residue_indices[:12], np.flip(residue_indices)[:12])).T


def check_output(computed_basepairs, basepairs):
    """
    Check the output of base_pairs.
    """

    # Check if basepairs are unique in computed_basepairs
    seen = set()
    assert (not any(
        (base1, base2) in seen) or (base2, base1 in seen)
        or seen.add((base1, base2)) for base1, base2 in computed_basepairs
        )
    # Check if the right number of basepairs is in computed_basepairs
    assert(len(computed_basepairs) == len(basepairs))
    # Check if the right basepairs are in computed_basepairs
    for comp_basepair in computed_basepairs:
        assert ((comp_basepair in basepairs) \
                or (comp_basepair in np.flip(basepairs)))


@pytest.mark.parametrize("unique_bool", [False, True])
def test_base_pairs_forward(nuc_sample_array, basepairs, unique_bool):
    """
    Test for the function base_pairs.
    """
    computed_basepairs = struc.base_pairs(nuc_sample_array, unique=unique_bool)
    check_output(nuc_sample_array[computed_basepairs].res_id, basepairs)


def test_base_pairs_forward_no_hydrogen(nuc_sample_array, basepairs):
    """
    Test for the function base_pairs with the hydrogens removed from the
    test structure.
    """
    nuc_sample_array = nuc_sample_array[nuc_sample_array.element != "H"]
    computed_basepairs = struc.base_pairs(nuc_sample_array)
    check_output(nuc_sample_array[computed_basepairs].res_id, basepairs)


@pytest.mark.parametrize("unique_bool", [False, True])
def test_base_pairs_reverse(nuc_sample_array, basepairs, unique_bool):
    """
    Reverse the order of residues in the atom_array and then test the
    function base_pairs.
    """

    # Reverse sequence of residues in nuc_sample_array
    reversed_nuc_sample_array = struc.AtomArray(0)
    for residue in reversed_iterator(struc.residue_iter(nuc_sample_array)):
        reversed_nuc_sample_array = reversed_nuc_sample_array + residue

    computed_basepairs = struc.base_pairs(
        reversed_nuc_sample_array, unique=unique_bool
    )
    check_output(
        reversed_nuc_sample_array[computed_basepairs].res_id, basepairs
    )


def test_base_pairs_reverse_no_hydrogen(nuc_sample_array, basepairs):
    """
    Remove the hydrogens from the sample structure. Then reverse the
    order of residues in the atom_array and then test the function
    base_pairs.
    """
    nuc_sample_array = nuc_sample_array[nuc_sample_array.element != "H"]
    # Reverse sequence of residues in nuc_sample_array
    reversed_nuc_sample_array = struc.AtomArray(0)
    for residue in reversed_iterator(struc.residue_iter(nuc_sample_array)):
        reversed_nuc_sample_array = reversed_nuc_sample_array + residue

    computed_basepairs = struc.base_pairs(reversed_nuc_sample_array)
    check_output(
        reversed_nuc_sample_array[computed_basepairs].res_id, basepairs
    )


@pytest.mark.parametrize("seed", range(10))
def test_base_pairs_reordered(nuc_sample_array, seed):
    """
    Test the function base_pairs with structure where the atoms are not
    in the RCSB-Order.
    """
    # Randomly reorder the atoms in each residue
    nuc_sample_array_reordered = struc.AtomArray(0)
    np.random.seed(seed)

    for residue in struc.residue_iter(nuc_sample_array):
        bound = residue.array_length()
        indices = np.random.choice(
            np.arange(bound), bound,replace=False
        )
        nuc_sample_array_reordered += residue[..., indices]

    assert(np.all(
        struc.base_pairs(nuc_sample_array)
        == struc.base_pairs(nuc_sample_array_reordered)
    ))


def test_map_nucleotide():
    """Test the function map_nucleotide with some examples.
    """
    pyrimidines = ['C', 'T', 'U']
    purines = ['A', 'G']

    # Test that the standard bases are correctly identified
    assert struc.map_nucleotide(residue('U')) == ('U', True)
    assert struc.map_nucleotide(residue('A')) == ('A', True)
    assert struc.map_nucleotide(residue('T')) == ('T', True)
    assert struc.map_nucleotide(residue('G')) == ('G', True)
    assert struc.map_nucleotide(residue('C')) == ('C', True)

    # Test that some non_standard nucleotides are mapped correctly to
    # pyrimidine/purine references
    psu_tuple = struc.map_nucleotide(residue('PSU'))
    assert psu_tuple[0] in pyrimidines
    assert psu_tuple[1] == False

    psu_tuple = struc.map_nucleotide(residue('3MC'))
    assert psu_tuple[0] in pyrimidines
    assert psu_tuple[1] == False

    i_tuple = struc.map_nucleotide(residue('I'))
    assert i_tuple[0] in purines
    assert i_tuple[1] == False

    m7g_tuple = struc.map_nucleotide(residue('M7G'))
    assert m7g_tuple[0] in purines
    assert m7g_tuple[1] == False

    assert struc.map_nucleotide(residue('ALA')) is None

def get_reference(pdb_id):
    """Gets the reference edges from specified pdb files
    """
    reference = strucio.load_structure(
        join(data_dir("structure"), f"base_pairs/{pdb_id}.cif")
    )

    with open(
        join(data_dir("structure"), f"base_pairs/{pdb_id}.json"
    ), "r") as file:
        edges = np.array(json.load(file))
    return reference, edges


def check_edge_plausibility(
    reference_structure, pair, reference_edges, output_edges
):
    # Get the complete edge matrix for a given edge
    edge_matrix = _get_edge_matrix(
        reference_structure, get_residue_masks(reference_structure, pair)
    )
    # Check if the difference to the reference is at least arbitrary
    for edges, reference_edge, output_edge in zip(
        edge_matrix, reference_edges, output_edges
    ):
        max_matches = np.max(edges)
        max_match_edges = np.argwhere(edges == max_matches).flatten()
        assert reference_edge in max_match_edges
        assert output_edge in max_match_edges


@pytest.mark.parametrize("pdb_id", ["1gid", "1nkw", "1xnr"])
def test_base_pairs_edge(pdb_id):
    # Get the references
    reference_structure, reference_edges = get_reference(pdb_id)
    # Calculate basepairs and edges for the references
    pairs = struc.base_pairs(reference_structure)
    edges = struc.base_pairs_edge(reference_structure, pairs)

    # Check the plausibility with the reference data for each basepair
    for pair, pair_edges in zip(pairs, edges):
        pair_res_ids = reference_structure[pair].res_id
        if (
            np.any(
                np.logical_and(
                    reference_edges[:, 0] == pair_res_ids[0],
                    reference_edges[:, 1] == pair_res_ids[1]
                )

            )
        ):
            index = np.where(np.logical_and(
                    reference_edges[:, 0] == pair_res_ids[0],
                    reference_edges[:, 1] == pair_res_ids[1]
                ))
            pair_reference_edges =  [
                reference_edges[index, 2], reference_edges[index, 3]
            ]
            check_edge_plausibility(
                reference_structure, pair, pair_reference_edges, pair_edges
            )

        elif (
            np.any(
                np.logical_and(
                    reference_edges[:, 1] == pair_res_ids[0],
                    reference_edges[:, 0] == pair_res_ids[1]
                )

            )
        ):
            index = np.where(np.logical_and(
                    reference_edges[:, 1] == pair_res_ids[0],
                    reference_edges[:, 0] == pair_res_ids[1]
                ))
            pair_reference_edges =  [
                reference_edges[index, 3], reference_edges[index, 2]
            ]
            check_edge_plausibility(
                reference_structure, pair, pair_reference_edges, pair_edges
            )

def get_reference_orientation(pdb_id):
    """Gets the reference sugars from specified pdb files
    """
    reference = strucio.load_structure(
        join(data_dir("structure"), f"base_pairs/{pdb_id}.cif")
    )

    with open(
        join(data_dir("structure"), f"base_pairs/{pdb_id}_sugar.json"
    ), "r") as file:
        sugar_orientations = np.array(json.load(file))
    return reference, sugar_orientations

@pytest.mark.parametrize("pdb_id", ["1gid", "1nkw"])
def test_base_pairs_glycosidic_bonds(pdb_id):
    # Get the references
    reference_structure, reference_gly_bonds = get_reference_orientation(
        pdb_id
    )
    # Calculate basepairs and edges for the references
    pairs = struc.base_pairs(reference_structure)
    glycosidic_bond_orientations = struc.base_pairs_glycosidic_bonds(
        reference_structure, pairs
    )

    # Check the plausibility with the reference data for each basepair
    for pair, pair_orientation in zip(pairs, glycosidic_bond_orientations):
        pair_res_ids = reference_structure[pair].res_id
        if (
            np.any(
                np.logical_and(
                    reference_gly_bonds[:, 0] == pair_res_ids[0],
                    reference_gly_bonds[:, 1] == pair_res_ids[1]
                )
            )
        ):
            index = np.where(np.logical_and(
                    reference_gly_bonds[:, 0] == pair_res_ids[0],
                    reference_gly_bonds[:, 1] == pair_res_ids[1]
                ))
            reference_orientation = struc.glycosidic_bond(
                reference_gly_bonds[index, 2]
            )
            assert reference_orientation == pair_orientation
        elif (
            np.any(
                np.logical_and(
                    reference_gly_bonds[:, 1] == pair_res_ids[0],
                    reference_gly_bonds[:, 0] == pair_res_ids[1]
                )
            )
        ):
            index = np.where(np.logical_and(
                    reference_gly_bonds[:, 1] == pair_res_ids[0],
                    reference_gly_bonds[:, 0] == pair_res_ids[1]
                ))
            reference_orientation = struc.glycosidic_bond(
                reference_gly_bonds[index, 2]
            )
            assert reference_orientation == pair_orientation

def test_base_stacking():
    """
    Test ``base_stacking()`` using the DNA-double-helix 1BNA. It is
    expected that adjacent bases are stacked. However, due to
    distortions in the helix there are exception for this particular
    helix.
    """
    # Load the test structure (1BNA) - a DNA-double-helix
    helix = strucio.load_structure(join(data_dir("structure"), "1bna.mmtf"))

    # For a DNA-double-helix it is expected that adjacent bases are
    # stacked.
    expected_stackings = []
    for i in range(1, 24):
        expected_stackings.append([i, i+1])

    # Due to distortions in the helix not all adjacent bases have a
    # geometry that meets the criteria of `base_stacking`.
    expected_stackings.remove([10, 11])
    expected_stackings.remove([12, 13])
    expected_stackings.remove([13, 14])

    stacking = helix[struc.base_stacking(helix)].res_id

    assert len(struc.base_stacking(helix)) == len(expected_stackings)

    for interaction in stacking:
        assert list(interaction) in expected_stackings


