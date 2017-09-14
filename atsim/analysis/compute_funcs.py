import copy
import numpy as np
from atsim import utils
from atsim.utils import dict_from_list
from atsim.readwrite import format_list, format_dict


# Variables which do not need to be parameterised:
PREDEFINED_VARS = {
    'gb_area': {
        'type': 'compute',
        'name': 'gb_area',
        'id': 'gb_area',
    },
    'gb_boundary_vac': {
        'type': 'compute',
        'name': 'gb_boundary_vac',
        'id': 'gb_boundary_vac',
    },
    'sup_type': {
        'type': 'compute',
        'name': 'supercell_type',
        'id': 'supercell_type',
    },
    'gb_dist_initial': {
        'type': 'compute',
        'name': 'atoms_gb_dist_initial',
        'id': 'atoms_gb_dist_initial',
    },
    'gb_dist_final': {
        'type': 'compute',
        'name': 'atoms_gb_dist_final',
        'id': 'atoms_gb_dist_final',
    },
    'gb_dist_change': {
        'type': 'compute',
        'name': 'atoms_gb_dist_change',
        'id': 'atoms_gb_dist_change',
    },
}


def is_bicrystal(sim):
    """
    Check if a simulation structure represents a bicrystal

    Notes
    -----
    The check in sim.options is for simulations generated before mid-
    September 2017.

    """
    if hasattr(sim.structure, 'meta'):
        if 'bicrystal' in sim.structure.meta['supercell_type']:
            return True

    elif sim.options['base_structure']['type'] == 'CSLBicrystal':
        return True

    else:
        return False


def get_depends(compute_name, inc_id=True, inc_val=True, **kwargs):
    """
    For a given compute, check if it has any dependencies. If it does,
    return a list of those as new definitions, in addition to the specified
    compute, in the correct dependency order.

    Parameters
    ----------


    """
    # Validation:
    allowed_computes = (list(SINGLE_COMPUTE_LOOKUP.keys()) +
                        list(MULTI_COMPUTE_LOOKUP.keys()))

    if compute_name not in allowed_computes:
        raise ValueError('Compute "{}" is not allowed.'.format(compute_name))

    d = {
        'type': 'compute',
        'name': compute_name,
    }
    if inc_id:
        d.update({'id': compute_name})

    out = []
    if compute_name == 'gb_energy':

        d.update({
            'energy_src': kwargs['energy_src'],
            'opt_step': kwargs['opt_step'],
            'series_id': kwargs['series_id'],
            'unit': kwargs['unit'],
        })
        out = (get_depends('energy', inc_id=inc_id, inc_val=inc_val,
                           energy_src=kwargs['energy_src'],
                           opt_step=kwargs['opt_step']) +
               get_depends('num_atoms', inc_id=inc_id, inc_val=inc_val) +
               [PREDEFINED_VARS['gb_area'],
                PREDEFINED_VARS['sup_type']]
               ) + out

    elif compute_name == 'energy_per_atom':

        d.update({
            'energy_src': kwargs['energy_src'],
            'opt_step': kwargs['opt_step']
        })
        out = (get_depends('num_atoms', inc_id=inc_id, inc_val=inc_val) +
               get_depends('energy', inc_id=inc_id, inc_val=inc_val,
                           energy_src=kwargs['energy_src'],
                           opt_step=kwargs['opt_step']) + out)

    elif compute_name == 'gamma_surface_info':

        d.update({
            'info_name': kwargs['info_name'],
        })

        csi_idx = {
            'name': 'csi_idx',
            'type': 'series_id',
            'col_id': 'relative_shift',
        }
        grid_idx = {
            'type': 'series_id',
            'name': 'grid_idx',
            'col_id': 'relative_shift'
        }
        point_idx = {
            'type': 'series_id',
            'name': 'point_idx',
            'col_id': 'relative_shift'
        }

        add_out = [csi_idx, grid_idx, point_idx]
        ids = ['csi_idx', 'grid_idx', 'point_idx']
        for i, j in zip(add_out, ids):
            if inc_id:
                i.update({'id': j})

        out = add_out + out

    elif compute_name == 'master_gamma':

        d.update({
            'energy_src': kwargs['energy_src'],
            'opt_step': kwargs['opt_step'],
            'series_id': kwargs['series_id'],
            'unit': kwargs['unit'],
        })

        out = (get_depends('gb_energy', inc_id=inc_id, inv_val=inc_val,
                           energy_src=kwargs['energy_src'],
                           opt_step=kwargs['opt_step'],
                           series_id=kwargs['series_id'],
                           unit=kwargs['unit']) +
               get_depends('gamma_surface_info', inc_id=inc_id, inv_val=inc_val,
                           info_name='row_idx') +
               get_depends('gamma_surface_info', inc_id=inc_id, inv_val=inc_val,
                           info_name='col_idx') +
               get_depends('gamma_surface_info', inc_id=inc_id, inv_val=inc_val,
                           info_name='x_std_vals') +
               get_depends('gamma_surface_info', inc_id=inc_id, inv_val=inc_val,
                           info_name='y_std_vals') +
               get_depends('gamma_surface_info', inc_id=inc_id, inv_val=inc_val,
                           info_name='x_frac_vals') +
               get_depends('gamma_surface_info', inc_id=inc_id, inv_val=inc_val,
                           info_name='y_frac_vals') +
               get_depends('gamma_surface_info', inc_id=inc_id, inv_val=inc_val,
                           info_name='grid_shape')
               ) + [PREDEFINED_VARS['gb_boundary_vac']] + out

    elif compute_name == 'energy':

        d.update({
            'energy_src': kwargs['energy_src'],
        })
        opt_step = kwargs.get('opt_step')
        if opt_step is not None:
            d.update({
                'opt_step': opt_step,
            })

    elif compute_name == 'atoms_gb_dist_change':

        out = [
            PREDEFINED_VARS['gb_dist_initial'],
            PREDEFINED_VARS['gb_dist_final'],
            PREDEFINED_VARS['sup_type'],
        ] + out

    # If the d dict is not in out, add it:
    d_out = dict_from_list(out, d)
    if d_out is None:
        out += [d]

    # Add a vals key to each dict if inc_val is True:
    for v_idx, v in enumerate(out):
        if v.get('vals') is None and inc_val:
            out[v_idx].update({'vals': []})
        elif v.get('vals') is not None and not inc_val:
            del out[v_idx]['vals']

    return out


def num_atoms(out, sim, sim_idx):
    return sim.structure.num_atoms


def supercell_type(out, sim, sim_idx):
    """
    Get the supercell type.

    Notes
    -----
    It is neccessary for this to be a "compute" rather than a "parameter"
    for compatibility reasons.

    """

    COMPATIBILITY_LOOKUP = {
        'CSLBicrystal': 'bicrystal',
        'CSLBulkBicrystal': 'bulk',
        'CSLSurfaceBicrystal': 'surface',
        'BulkCrystal': 'bulk',
    }

    if hasattr(sim.structure, 'meta'):
        return sim.structure.meta['supercell_type'][0]

    else:
        return COMPATIBILITY_LOOKUP[sim.options['base_structure']['type']]


def energy(out, sim, sim_idx, energy_src, opt_step=None):

    # Validation
    err_msg = 'Energy source: "{}" not available from {} output.'
    method = sim.options['method']
    allowed_en_srcs = {
        'castep': ['final_energy', 'final_fenergy', 'final_zenergy'],
        'lammps': ['final_energy'],
    }
    if energy_src not in allowed_en_srcs[method]:
        raise ValueError(err_msg.format(energy_src, method.upper()))

    energy = sim.results[energy_src]

    if opt_step is None:
        return energy
    else:
        if not isinstance(opt_step, int):
            raise ValueError('`opt_step` must be an integer.')
        return energy[opt_step]


def energy_per_atom(out, sim, sim_idx, energy_src, opt_step=None):

    rv_args = {
        'compute_name': 'energy_per_atom',
        'inc_id': False,
        'inc_val': False,
        'energy_src': energy_src,
        'opt_step': opt_step,
    }
    req_vars_defn = get_depends(**rv_args)
    vrs = out['variables']
    req_vars = [dict_from_list(vrs, i) for i in req_vars_defn]
    n = req_vars[0]['vals'][sim_idx]
    e = req_vars[1]['vals'][sim_idx]
    return e / n


def gb_area(out, sim, sim_idx):

    if is_bicrystal(sim):
        return sim.structure.boundary_area
    else:
        return None


def gb_boundary_vac(out, sim, sim_idx):

    if is_bicrystal(sim):
        return sim.structure.boundary_vac
    else:
        return None


def gb_thickness(out, sim, sim_idx):

    if is_bicrystal(sim):
        return sim.structure.bicrystal_thickness
    else:
        return None


def atoms_gb_dist_initial(out, sim, sim_idx):

    if is_bicrystal(sim):
        return sim.structure.atoms_gb_dist
    else:
        return None


def atoms_gb_dist_final(out, sim, sim_idx):

    if is_bicrystal(sim):

        if sim.options['method'] == 'lammps':
            atom_sites_final = sim.results['atoms'][-1]
        elif sim.options['method'] == 'castep':
            atom_sites_final = sim.results['geom']['ions'][-1]

        n_unit = sim.structure.n_unit
        gb_dist = np.einsum('jk,jl->k', atom_sites_final, n_unit)

        return gb_dist

    else:
        return None


def atoms_gb_dist_change(out, sim, sim_idx):

    rv_args = {
        'compute_name': 'atoms_gb_dist_change',
        'inc_id': False,
        'inc_val': False,
    }
    req_vars_defn = get_depends(**rv_args)
    vrs = out['variables']
    req_vars = [dict_from_list(vrs, i) for i in req_vars_defn]

    atoms_gb_dist_initial = req_vars[0]['vals'][sim_idx]
    atoms_gb_dist_final = req_vars[1]['vals'][sim_idx]
    sup_type = req_vars[2]['vals'][sim_idx]

    if is_bicrystal(sim):
        return np.array(atoms_gb_dist_final) - np.array(atoms_gb_dist_initial)


def gb_energy(out, req_vars):
    """
    Computes the grain boundary energy for multiple simulations.

    Parameters
    ----------
    out : dict
        Output dict in which to save the output GB energies.
    series_id : str
        Series name used to match bulk and grain boundary supercells for GB
        energy computation. Can either be a series name or a variable ID.
    energy_src : str
        Energy key from the simulation output dict to use in the GB energy
        computation.
    opt_step : int
        Optimisation step from which to take the energies in the GB energy
        computation.

    """

    energy, num_atoms, area, sup_type = [req_vars[i]['vals'] for i in range(4)]
    series_names = out['series_name']
    series_id = req_vars[-1]['series_id']
    unit = req_vars[-1]['unit']
    sesh_ids = np.array(out['session_id'])[out['session_id_idx']]
    num_sims = len(sesh_ids)

    srs_vals = []
    for i in series_id:
        if i in series_names:
            i_idx = series_names.index(i)
            i_vals = utils.get_col(out['series_id']['val'], i_idx)
        else:
            i_vals = dict_from_list(
                out['variables'], {'id': i})['vals']
        srs_vals.append(i_vals)
    srs_vals = utils.transpose_list(srs_vals)

    if len(srs_vals) == 0:
        srs_vals = [[0] for _ in range(num_sims)]

    gb_idx = []
    bulk_idx = []
    for i_idx, i in enumerate(sup_type):
        if i == 'bicrystal':
            gb_idx.append(i_idx)
        elif i == 'bulk':
            bulk_idx.append(i_idx)

    all_E_gb = [None, ] * num_sims
    for gb_i in gb_idx:
        E_gb = None
        for bulk_i in bulk_idx:
            if srs_vals[gb_i] == srs_vals[bulk_i]:
                gb_num = num_atoms[gb_i]
                bulk_num = num_atoms[bulk_i]
                bulk_frac = gb_num / bulk_num
                E_gb = (energy[gb_i] - bulk_frac *
                        energy[bulk_i]) / (2 * area[gb_i])

        if E_gb is not None:
            if unit == 'J/m^2':
                E_gb *= 16.02176565
            all_E_gb[gb_i] = E_gb
    req_vars[-1]['vals'] = all_E_gb


def gamma_surface_info(out, req_vars, common_series_info):

    all_gamma_infos = {
        'row_idx': [],
        'col_idx': [],
        'x_std_vals': [],
        'y_std_vals': [],
        'x_frac_vals': [],
        'y_frac_vals': [],
        'x_num_den_vals': [],
        'y_num_den_vals': [],
        'grid_shape': [],
    }
    allowed_names = list(all_gamma_infos.keys())

    info_name = req_vars[-1]['info_name']
    if info_name not in all_gamma_infos:
        raise ValueError('compute_gamma_info: info_name "{}" not understood. '
                         'Must be one of: {}'.format(info_name, allowed_names))

    sesh_id_idx = out['session_id_idx']
    csi_idx, grid_idx, point_idx = [req_vars[i]['vals'] for i in range(3)]

    # Loop through each sim, identified by session id to which it belongs
    for sii_idx, sii in enumerate(sesh_id_idx):

        csi_exists = False
        try:
            csi = common_series_info[sii][csi_idx[sii_idx]]
            csi_exists = True
        except:
            pass

        if csi_exists:

            grid_exists = False
            try:
                grid = csi['grids'][grid_idx[sii_idx]]
                grid_exists = True
            except:
                pass

            if grid_exists:

                all_ri = grid['row_idx']
                all_ci = grid['col_idx']
                shp = grid['shape']
                all_x_std, all_y_std = grid['grid_points_std']
                all_x_frac, all_y_frac = grid['grid_points_frac']
                all_x_num_den, all_y_num_den = grid['grid_points_num_den']

                pnt_idx = point_idx[sii_idx]

                ri = all_ri[pnt_idx]
                ci = all_ci[pnt_idx]
                x_std = all_x_std[pnt_idx]
                y_std = all_y_std[pnt_idx]
                x_frac = all_x_frac[pnt_idx]
                y_frac = all_y_frac[pnt_idx]
                x_num_den = all_x_num_den[pnt_idx]
                y_num_den = all_y_num_den[pnt_idx]

        if not csi_exists or not grid_exists:
            shp = None
            ri = None
            ci = None
            x_std = None
            y_std = None
            x_frac = None
            y_frac = None
            x_num_den = None
            y_num_den = None

        all_gamma_infos['row_idx'].append(ri)
        all_gamma_infos['col_idx'].append(ci)
        all_gamma_infos['x_std_vals'].append(x_std)
        all_gamma_infos['y_std_vals'].append(y_std)
        all_gamma_infos['x_frac_vals'].append(x_frac)
        all_gamma_infos['y_frac_vals'].append(y_frac)
        all_gamma_infos['x_num_den_vals'].append(x_num_den)
        all_gamma_infos['y_num_den_vals'].append(y_num_den)
        all_gamma_infos['grid_shape'].append(shp)

    req_vars[-1]['vals'] = all_gamma_infos[info_name]


def master_gamma(out, req_vars):

    (energy, num_atoms, gb_area, sup_type, gb_energy, csi_idx,
     grid_idx, point_idx, row_idx, col_idx, x_std_vals,
     y_std_vals, x_frac_vals, y_frac_vals, grid_shape,
     boundary_vac) = [req_vars[i]['vals'] for i in range(16)]

    print('energy: {}'.format(energy))
    print('num_atoms: {}'.format(num_atoms))
    print('gb_area: {}'.format(gb_area))
    print('sup_type: {}'.format(sup_type))
    print('gb_energy: {}'.format(gb_energy))

    print('csi_idx: {}'.format(csi_idx))
    print('grid_idx: {}'.format(grid_idx))
    print('point_idx: {}'.format(point_idx))

    print('row_idx: {}'.format(row_idx))
    print('col_idx: {}'.format(col_idx))
    print('x_std_vals: {}'.format(x_std_vals))
    print('y_std_vals: {}'.format(y_std_vals))
    print('x_frac_vals: {}'.format(x_frac_vals))
    print('y_frac_vals: {}'.format(y_frac_vals))
    print('grid_shape: {}'.format(grid_shape))
    print('boundary_vac: {}'.format(boundary_vac))

    num_sims = len(gb_energy)

    # Get first valid gamma shape:
    for en_idx, en in enumerate(gb_energy):
        if en is not None:
            shp = grid_shape[en_idx]
            break

    all_E = {}
    X = np.ones(tuple(shp), dtype=float) * np.nan
    Y = np.ones(tuple(shp), dtype=float) * np.nan
    XY_frac = np.ones(tuple(shp) + (2,), dtype=float) * np.nan
    first_en_idx = np.ones(tuple(shp), dtype=float) * np.nan

    for en_idx, en in enumerate(gb_energy):

        if en is None:
            continue

        ri = row_idx[en_idx]
        ci = col_idx[en_idx]
        srs_v = boundary_vac[en_idx]
        print('srs_v: {}, type(srs_v): {}'.format(srs_v, type(srs_v)))

        if all_E.get(srs_v) is None:
            blank = np.ones(tuple(shp), dtype=float) * np.nan
            all_E.update({srs_v: blank})

        all_E[srs_v][ri, ci] = en

        if np.isnan(X[ri][ci]):
            X[ri, ci] = x_std_vals[en_idx]
            Y[ri, ci] = y_std_vals[en_idx]
            XY_frac[ri, ci] = [x_frac_vals[en_idx], y_frac_vals[en_idx]]
            first_en_idx[ri, ci] = en_idx

    # Fitting
    nrows = shp[0]
    ncols = shp[1]
    fit_grid_E = [[[] for i in range(ncols)] for _ in range(nrows)]
    fit_grid_vac = [[[] for i in range(ncols)] for _ in range(nrows)]

    fitted_E = np.ones((nrows, ncols), dtype=float) * np.nan
    fitted_vac = np.ones((nrows, ncols), dtype=float) * np.nan
    fitted_p1d = np.ones((nrows, ncols, 3), dtype=float) * np.nan

    for ri in range(nrows):
        for ci in range(ncols):
            for k, v in sorted(all_E.items()):

                fit_grid_E[ri][ci].append(v[ri][ci])
                fit_grid_vac[ri][ci].append(k)

            x = np.array(fit_grid_vac[ri][ci])
            y = np.array(fit_grid_E[ri][ci])

            # Get nonNaN values from y
            y_fin_idx = np.isfinite(y)
            y = y[y_fin_idx]
            x = x[y_fin_idx]

            if len(x) > 2:
                z = np.polyfit(x, y, 2)
                p1d = np.poly1d(z)
                dpdx = np.polyder(p1d)
                min_x = -dpdx[0] / dpdx[1]
                min_y = p1d(min_x)

                fitted_vac[ri, ci] = min_x
                fitted_E[ri, ci] = min_y
                fitted_p1d[ri, ci] = p1d.coeffs

    first_en_idx = first_en_idx.reshape(-1,).astype(int)

    fitted_p1d = fitted_p1d.reshape(-1, 3)
    all_fitted_p1d = np.ones((num_sims, 3), dtype=float) * np.nan
    all_fitted_p1d[first_en_idx] = fitted_p1d

    E_min_flat = fitted_E.reshape(-1)
    all_E_min_flat = np.ones((num_sims,), dtype=float) * np.nan
    all_E_min_flat[first_en_idx] = E_min_flat

    vac_min_flat = fitted_vac.reshape(-1)
    all_vac_min_flat = np.ones((num_sims,), dtype=float) * np.nan
    all_vac_min_flat[first_en_idx] = vac_min_flat

    req_vars[-1]['vals'] = {
        'X': X.tolist(),
        'Y': Y.tolist(),
        'XY_frac': XY_frac.tolist(),
        'E': {k: v.tolist() for k, v in all_E.items()},
        'E_min': fitted_E.tolist(),
        'vac_min': fitted_vac.tolist(),
        'fits': all_fitted_p1d.tolist(),
        'vac_min_flat': all_vac_min_flat.tolist(),
        'E_min_flat': all_E_min_flat.tolist(),
    }


# Single-compute functions are passed individual AtomisticSimulation objects:
SINGLE_COMPUTE_LOOKUP = {
    'num_atoms': num_atoms,
    'energy': energy,
    'energy_per_atom': energy_per_atom,
    'gb_area': gb_area,
    'supercell_type': supercell_type,
    'gb_thickness': gb_thickness,
    'gb_boundary_vac': gb_boundary_vac,
    'atoms_gb_dist_initial': atoms_gb_dist_initial,
    'atoms_gb_dist_final': atoms_gb_dist_final,
    'atoms_gb_dist_change': atoms_gb_dist_change,
    # 'atoms_gb_dist_δ': atoms_gb_dist_δ,
}

# Multi-compute functions are passed the whole output dict of harvest.py as it
# is being constructed:
MULTI_COMPUTE_LOOKUP = {
    'gb_energy': gb_energy,
    'gamma_surface_info': gamma_surface_info,
    'master_gamma': master_gamma,
}
