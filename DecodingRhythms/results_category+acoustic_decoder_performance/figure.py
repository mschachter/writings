import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2

from DecodingRhythms.utils import set_font, COLOR_BLUE_LFP, COLOR_YELLOW_SPIKE, clean_region, COLOR_RED_SPIKE_RATE
from lasp.plots import multi_plot, custom_legend, grouped_boxplot
from utils import get_this_dir
from zeebeez.aggregators.lfp_and_spike_psd_decoders import AggregateLFPAndSpikePSDDecoder
from zeebeez.utils import CALL_TYPE_SHORT_NAMES, DECODER_CALL_TYPES


def export_dfs(agg, data_dir='/auto/tdrive/mschachter/data'):

    freqs = agg.freqs
    # read electrode data
    edata = pd.read_csv(os.path.join(data_dir, 'aggregate', 'electrode_data.csv'))

    # initialize multi electrode dataset dictionary
    multi_electrode_data = {'bird':list(), 'block':list(), 'segment':list(), 'hemi':list(), 'band':list()}
    anames = agg.acoustic_props + ['category']
    for aprop in anames:
        for t in ['lfp', 'spike', 'spike_rate']:
            multi_electrode_data['perf_%s_%s' % (aprop, t)] = list()
            if t != 'spike_rate':
                multi_electrode_data['lkrat_%s_%s' % (aprop, t)] = list()

    # initialize single electrode dataset dictionary
    single_electrode_data = {'bird':list(), 'block':list(), 'segment':list(), 'hemi':list(), 'electrode':list(),
                             'region':list()}

    anames = agg.acoustic_props + ['category']
    for aprop in anames:
        single_electrode_data['perf_%s' % aprop] = list()
        single_electrode_data['lkrat_%s' % aprop] = list()

    # initialize single cell dataset dictionary
    cell_data = {'bird':list(), 'block':list(), 'segment':list(), 'hemi':list(), 'electrode':list(),
                 'region':list(), 'cell_index':list()}
    for aprop in anames:
        cell_data['perf_%s' % aprop] = list()
        cell_data['lkrat_%s' % aprop] = list()

    nbands = len(freqs)
    i = agg.df.bird != 'BlaBro09xxF'
    g = agg.df[i].groupby(['bird', 'block', 'segment', 'hemi'])

    for (bird,block,segment,hemi),gdf in g:

        wtup = (bird,block,segment,hemi)
        index2electrode = agg.index2electrode[wtup]
        cell_index2electrode = agg.cell_index2electrode[wtup]

        # compute the number of cells, use it to compute significance thresholds for the likelihood ratios
        i = (gdf.e1 != -1) & (gdf.e1 == gdf.e2) & (gdf.cell_index != -1) & (gdf.decomp == 'spike_psd') & \
            (gdf.exel == False) & (gdf.exfreq == False) & (gdf.aprop == 'q2')
        ncells = i.sum()
        # print '%s,%s,%s,%s # of cells: %d' % (bird, block, segment, hemi, ncells)

        x = np.linspace(1, 500, 5000)
        # compute significance threshold for LFP when frequency bands are held out, for acoustic decoder
        dof = 16
        p = chi2.pdf(x, dof)
        sig_thresh_lfp_freq_acoustic = min(x[p > 0.01])

        # compute significance threshold for LFP when frequency bands are held out, for category decoder
        dof = 16*8
        p = chi2.pdf(x, dof)
        sig_thresh_lfp_freq_cat = min(x[p > 0.01])
        print 'sig_thresh_lfp_freq_cat=%f' % sig_thresh_lfp_freq_cat

        # compute significance threshold for spikes when frequency bands are held out, for acoustic decoder
        dof = ncells
        p = chi2.pdf(x, dof)
        sig_thresh_spikes_freq_acoustic = min(x[p > 0.01])

        # compute significance threshold for spikes when frequency bands are held out, for category decoder
        dof = ncells*8
        p = chi2.pdf(x, dof)
        sig_thresh_spikes_freq_cat = min(x[p > 0.01])

        # compute significance threshold for LFP or spikes when an electrode or cell is held out, for acoustic decoder
        dof = len(freqs)
        p = chi2.pdf(x, dof)
        sig_thresh_electrode_or_cell_acoustic = min(x[p > 0.01])

        # compute significance threshold for LFP or spikes when an electrode or cell is held out, for category decoder
        dof = len(freqs)*8
        p = chi2.pdf(x, dof)
        sig_thresh_electrode_or_cell_cat = min(x[p > 0.01])

        # get the region by electrode
        electrode2region = dict()
        for e in index2electrode:
            i = (edata.bird == bird) & (edata.block == block) & (edata.hemisphere == hemi) & (edata.electrode == e)
            assert i.sum() == 1
            electrode2region[e] = clean_region(edata.region[i].values[0])

        # collect multi-electrode multi-band dataset
        band0_perfs = None
        for b in range(nbands+1):

            exfreq = b > 0

            perfs = dict()
            anames = agg.acoustic_props + ['category']
            for aprop in anames:
                for t,decomp in [('lfp', 'locked'), ('spike', 'spike_psd'), ('spike_rate', 'spike_rate')]:

                    if decomp == 'spike_rate' and b > 0:
                        perfs['perf_%s_%s' % (aprop, t)] = 0
                        continue

                    # get multielectrode LFP decoder performance
                    i = (gdf.e1 == -1) & (gdf.e2 == -1) & (gdf.cell_index == -1) & (gdf.band == b) & (gdf.exfreq == exfreq) & \
                        (gdf.exel == False) & (gdf.aprop == aprop) & (gdf.decomp == decomp)

                    if i.sum() != 1:
                        print "Zero or more than 1 result for (%s, %s, %s, %s), decomp=locked, band=%d: i.sum()=%d" % (bird, block, segment, hemi, b, i.sum())
                        continue

                    if aprop == 'category':
                        perfs['perf_%s_%s' % (aprop, t)] = gdf.pcc[i].values[0]
                    else:
                        perfs['perf_%s_%s' % (aprop, t)] = gdf.r2[i].values[0]

                    lk = gdf.likelihood[i].values[0]
                    if aprop == 'category':
                        nsamps = gdf.num_samps[i].values[0]
                        lk *= nsamps
                    perfs['lk_%s_%s' % (aprop, t)] = lk

            nperfs = np.sum([k.startswith('perf') for k in perfs.keys()])
            if nperfs != len(anames)*3:
                print 'nperfs=%d, b=%d (%s,%s,%s,%s), skipping...' % (nperfs, b, bird, block, segment, hemi)
                continue

            multi_electrode_data['bird'].append(bird)
            multi_electrode_data['block'].append(block)
            multi_electrode_data['segment'].append(segment)
            multi_electrode_data['hemi'].append(hemi)
            multi_electrode_data['band'].append(b)
            for k,v in perfs.items():
                if k.startswith('perf'):
                    multi_electrode_data[k].append(v)

            if b == 0:
                band0_perfs = perfs
                for aprop in anames:
                    for t in ['lfp', 'spike']:
                        multi_electrode_data['lkrat_%s_%s' % (aprop,t)].append(0)
            else:
                # compute the likelihood ratio for each acoustic property on this band
                for aprop in anames:
                    for t in ['lfp', 'spike']:
                        full_likelihood = band0_perfs['lk_%s_%s' % (aprop, t)]
                        leave_one_out_likelihood = perfs['lk_%s_%s' % (aprop, t)]
                        lkrat = 2*(leave_one_out_likelihood - full_likelihood)
                        if t == 'lfp' and aprop != 'category':
                            lkrat /= sig_thresh_lfp_freq_acoustic
                        elif t == 'lfp' and aprop == 'category':
                            lkrat /= sig_thresh_lfp_freq_cat
                        elif t == 'spike' and aprop != 'category':
                            lkrat /= sig_thresh_spikes_freq_acoustic
                        else:
                            lkrat /= sig_thresh_spikes_freq_cat

                        multi_electrode_data['lkrat_%s_%s' % (aprop, t)].append(lkrat)

        """
        # collect single electrode dataset
        for e in index2electrode:

            # get LFP performance data for this electrode, with and without leave-one-out (the variable "exel")
            perfs = dict()
            perfs_exel = dict()
            anames = agg.acoustic_props + ['category']
            for aprop in anames:
                for exel in [True, False]:
                    p = perfs
                    if exel:
                        p = perfs_exel
                    # get multielectrode LFP decoder performance
                    i = (gdf.e1 == e) & (gdf.e2 == e) & (gdf.cell_index == -1) & (gdf.band == 0) & (gdf.exfreq == False) & \
                        (gdf.exel == exel) & (gdf.aprop == aprop) & (gdf.decomp == 'locked')
                    assert i.sum() == 1, "Zero or more than 1 result for (%s, %s, %s, %s), decomp=locked, e=%d: i.sum()=%d" % (bird, block, segment, hemi, e, i.sum())
                    if aprop == 'category':
                        p['perf_%s' % aprop] = gdf.pcc[i].values[0]
                    else:
                        p['perf_%s' % aprop] = gdf.r2[i].values[0]

                    lk = gdf.likelihood[i].values[0]
                    if aprop == 'category':
                        nsamps = gdf.num_samps[i].values[0]
                        lk *= nsamps
                    p['lk_%s' % aprop] = lk

            # append the single electrode performances and likelihood ratios to the single electrode dataset
            single_electrode_data['bird'].append(bird)
            single_electrode_data['block'].append(block)
            single_electrode_data['segment'].append(segment)
            single_electrode_data['hemi'].append(hemi)
            single_electrode_data['electrode'].append(e)
            single_electrode_data['region'].append(electrode2region[e])

            for aprop in anames:
                # append single electrode peformance
                single_electrode_data['perf_%s' % aprop].append(perfs['perf_%s' % aprop])
                # append likelihood ratio
                full_likelihood = band0_perfs['lk_%s_%s' % (aprop, 'lfp')]
                leave_one_out_likelihood = perfs_exel['lk_%s' % aprop]
                lkrat = 2*(leave_one_out_likelihood - full_likelihood)
                lkrat /= sig_thresh_electrode_or_cell_acoustic
                single_electrode_data['lkrat_%s' % aprop].append(lkrat)

        # collect single cell dataset
        for e in index2electrode:

            # count the number of cells and get their indices
            i = (gdf.e1 == e) & (gdf.e2 == e) & (gdf.cell_index != -1) & (gdf.band == 0) & (gdf.exfreq == False) & \
                    (gdf.exel == False) & (gdf.decomp == 'spike_psd')
            if i.sum() == 0:
                print 'No cells for (%s, %s, %s, %s), e=%d' % (bird, block, segment, hemi, e)
                continue

            cell_indices = sorted(gdf[i].cell_index.unique())
            for ci in cell_indices:

                missing_data = False
                # get cell performance data for this electrode, with and without leave-one-out (the variable "exel")
                perfs = dict()
                perfs_exel = dict()
                anames = agg.acoustic_props + ['category']
                for aprop in anames:
                    for exel in [True, False]:
                        p = perfs
                        if exel:
                            p = perfs_exel

                        # get multielectrode LFP decoder performance
                        i = (gdf.e1 == e) & (gdf.e2 == e) & (gdf.cell_index == ci) & (gdf.band == 0) & (gdf.exfreq == False) & \
                            (gdf.exel == exel) & (gdf.aprop == aprop) & (gdf.decomp == 'spike_psd')
                        if i.sum() == 0:
                            print "No result for (%s, %s, %s, %s), decomp=spike_psd, e=%d, ci=%d: i.sum()=%d" % (bird, block, segment, hemi, e, ci, i.sum())
                            missing_data = True
                            continue
                        if i.sum() > 1:
                            print "More than 1 result for (%s, %s, %s, %s), decomp=spike_psd, e=%d, ci=%d: i.sum()=%d" % (bird, block, segment, hemi, e, ci, i.sum())
                            missing_data = True
                            continue

                        if aprop == 'category':
                            p['perf_%s' % aprop] = gdf.pcc[i].values[0]
                        else:
                            p['perf_%s' % aprop] = gdf.r2[i].values[0]

                        lk = gdf.likelihood[i].values[0]
                        if aprop == 'category':
                            nsamps = gdf.num_samps[i].values[0]
                            lk *= nsamps
                        p['lk_%s' % aprop] = lk

                if missing_data:
                    print 'Skipping cell %d on electrode %d for (%s, %s, %s, %s)' % (ci, e, bird, block, segment, hemi)
                    continue

                # append the single electrode performances and likelihood ratios to the single electrode dataset
                cell_data['bird'].append(bird)
                cell_data['block'].append(block)
                cell_data['segment'].append(segment)
                cell_data['hemi'].append(hemi)
                cell_data['electrode'].append(e)
                cell_data['region'].append(electrode2region[e])
                cell_data['cell_index'].append(ci)

                for aprop in anames:
                    # append single electrode peformance
                    cell_data['perf_%s' % aprop].append(perfs['perf_%s' % aprop])
                    # append likelihood ratio
                    full_likelihood = band0_perfs['lk_%s_%s' % (aprop, 'spike')]
                    leave_one_out_likelihood = perfs_exel['lk_%s' % aprop]
                    lkrat = 2*(leave_one_out_likelihood - full_likelihood)
                    lkrat /= sig_thresh_electrode_or_cell_acoustic
                    cell_data['lkrat_%s' % aprop].append(lkrat)
        """

    df_me = pd.DataFrame(multi_electrode_data)
    df_me.to_csv(os.path.join(data_dir, 'aggregate', 'multi_electrode_perfs.csv'), index=False)

    """
    df_se = pd.DataFrame(single_electrode_data)
    df_se.to_csv(os.path.join(data_dir, 'aggregate', 'single_electrode_perfs.csv'), index=False)

    df_cell = pd.DataFrame(cell_data)
    df_cell.to_csv(os.path.join(data_dir, 'aggregate', 'cell_perfs.csv'), index=False)
    """

    # return df_me,df_se,df_cell
    return None,None,None


def draw_category_perf_and_confusion(agg, df_me):
    df0 = df_me[df_me.band == 0]

    lfp_perfs = df0['perf_category_lfp'].values
    spike_perfs = df0['perf_category_spike'].values
    spike_rate_perfs = df0['perf_category_spike_rate'].values
    bp_data = {'Vocalization Type':[lfp_perfs, spike_perfs, spike_rate_perfs]}

    cmats = dict()

    for decomp in ['locked', 'spike_psd', 'spike_rate']:
        # compute average confusion matrix for spikes and LFP
        i = (agg.df.e1 == -1) & (agg.df.e2 == -1) & (agg.df.decomp == decomp) & (agg.df.band == 0) & \
            (agg.df.aprop == 'category') & (agg.df.exfreq == False) & (agg.df.exel == False)
        print '%s, i.sum()=%d' % (decomp, i.sum())

        df = agg.df[i]
        ci = df.cmat_index.values
        C = agg.confusion_matrices[ci, :, :]
        Cmean = C.mean(axis=0)

        cnames = agg.stim_class_names[ci][0]

        # reorder confusion matrix
        Cro = np.zeros_like(Cmean)
        for k,cname1 in enumerate(cnames):
            for j,cname2 in enumerate(cnames):
                i1 = DECODER_CALL_TYPES.index(cname1)
                i2 = DECODER_CALL_TYPES.index(cname2)
                Cro[i1, i2] = Cmean[k, j]
        cmats[decomp] = Cro

    figsize = (16, 12)
    fig = plt.figure(figsize=figsize)
    plt.subplots_adjust(top=0.95, bottom=0.05, left=0.05, right=0.99, hspace=0.40, wspace=0.20)

    # gs = plt.GridSpec(1, 100)
    gs = plt.GridSpec(2, 2)

    # make a boxplot
    ax = plt.subplot(gs[0, 0])
    grouped_boxplot(bp_data, subgroup_names=['LFP', 'Spike PSD', 'Spike Rate'],
                    subgroup_colors=[COLOR_BLUE_LFP, COLOR_YELLOW_SPIKE, COLOR_RED_SPIKE_RATE], box_spacing=1.5, ax=ax)
    plt.xticks([])
    plt.ylabel('PCC')
    plt.title('Vocalization Type Decoder Performance')

    # plot the mean LFP confusion matrix
    ax = plt.subplot(gs[0, 1])
    plt.imshow(cmats['locked'], origin='lower', interpolation='nearest', aspect='auto', vmin=0, vmax=1, cmap=plt.cm.afmhot)

    xtks = [CALL_TYPE_SHORT_NAMES[ct] for ct in DECODER_CALL_TYPES]
    plt.xticks(range(len(DECODER_CALL_TYPES)), xtks)
    plt.yticks(range(len(DECODER_CALL_TYPES)), xtks)
    plt.colorbar(label='PCC')
    plt.title('Mean LFP Decoder Confusion Matrix')

    # plot the mean spike confusion matrix
    ax = plt.subplot(gs[1, 0])
    plt.imshow(cmats['spike_psd'], origin='lower', interpolation='nearest', aspect='auto', vmin=0, vmax=1, cmap=plt.cm.afmhot)

    xtks = [CALL_TYPE_SHORT_NAMES[ct] for ct in DECODER_CALL_TYPES]
    plt.xticks(range(len(DECODER_CALL_TYPES)), xtks)
    plt.yticks(range(len(DECODER_CALL_TYPES)), xtks)
    plt.colorbar(label='PCC')
    plt.title('Mean Spike PSD Decoder Confusion Matrix')

    fname = os.path.join(get_this_dir(), 'perf_boxplots_category.svg')
    plt.savefig(fname, facecolor='w', edgecolor='none')

    # plot the mean spike rate confusion matrix
    ax = plt.subplot(gs[1, 1])
    plt.imshow(cmats['spike_rate'], origin='lower', interpolation='nearest', aspect='auto', vmin=0, vmax=1, cmap=plt.cm.afmhot)

    xtks = [CALL_TYPE_SHORT_NAMES[ct] for ct in DECODER_CALL_TYPES]
    plt.xticks(range(len(DECODER_CALL_TYPES)), xtks)
    plt.yticks(range(len(DECODER_CALL_TYPES)), xtks)
    plt.colorbar(label='PCC')
    plt.title('Mean Spike Rate Decoder Confusion Matrix')

    fname = os.path.join(get_this_dir(), 'perf_boxplots_category.svg')
    plt.savefig(fname, facecolor='w', edgecolor='none')


def draw_acoustic_perf_boxplots(agg, df_me):

    aprops_to_display = ['maxAmp', 'sal', 'meanspect', 'q1', 'q2', 'q3',
                         'entropyspect', 'meantime', 'entropytime']

    df0 = df_me[df_me.band == 0]

    bp_data = dict()
    for aprop in aprops_to_display:
        lfp_perfs = df0['perf_%s_lfp' % aprop].values
        spike_perfs = df0['perf_%s_spike' % aprop].values
        spike_rate_perfs = df0['perf_%s_spike_rate' % aprop].values
        bp_data[aprop] = [lfp_perfs, spike_perfs, spike_rate_perfs]

    figsize = (24, 10)
    fig = plt.figure(figsize=figsize)
    plt.subplots_adjust(top=0.95, bottom=0.05, left=0.05, right=0.99, hspace=0.40, wspace=0.20)

    grouped_boxplot(bp_data, group_names=aprops_to_display, subgroup_names=['LFP', 'Spike PSD', 'Spike Rate'],
                    subgroup_colors=[COLOR_BLUE_LFP, COLOR_YELLOW_SPIKE, COLOR_RED_SPIKE_RATE], box_spacing=1.5)

    plt.xlabel('Acoustic Feature')
    plt.ylabel('Decoder R2')

    fname = os.path.join(get_this_dir(), 'perf_boxplots.svg')
    plt.savefig(fname, facecolor='w', edgecolor='none')


def draw_perf_hists(agg, df_me):

    assert isinstance(agg, AggregateLFPAndSpikePSDDecoder)
    freqs = agg.freqs

    aprops_to_display = ['category', 'maxAmp', 'meanspect', 'stdspect', 'q1', 'q2', 'q3', 'skewspect', 'kurtosisspect',
                         'sal', 'entropyspect', 'meantime', 'stdtime', 'entropytime']

    # make histograms of performances across sites for each acoustic property
    perf_list = list()
    i = (df_me.band == 0)
    for aprop in aprops_to_display:
        lfp_perf = df_me[i]['perf_%s_%s' % (aprop, 'lfp')].values
        spike_perf = df_me[i]['perf_%s_%s' % (aprop, 'spike')].values

        perf_list.append({'lfp_perf':lfp_perf, 'spike_perf':spike_perf,
                          'lfp_mean':lfp_perf.mean(), 'spike_mean':spike_perf.mean(),
                          'aprop':aprop})

    # make plots
    print 'len(perf_list)=%d' % len(perf_list)

    def _plot_hist(pdata, ax):
        plt.sca(ax)
        plt.hist(pdata['lfp_perf'], bins=10, color='#00639E', alpha=0.7)
        plt.hist(pdata['spike_perf'], bins=10, color='#F1DE00', alpha=0.7)
        plt.legend(['LFP', 'Spike'], fontsize='x-small')
        plt.title(pdata['aprop'])
        if pdata['aprop'] == 'category':
            plt.xlabel('PCC')
        else:
            plt.xlabel('R2')
        plt.axis('tight')

    multi_plot(perf_list, _plot_hist, nrows=3, ncols=5, hspace=0.30, wspace=0.30)

    def _plot_scatter(pdata, ax):
        # pmax = max(pdata['lfp_perf'].max(), pdata['spike_perf'].max())
        pmax = 0.8
        plt.sca(ax)
        plt.plot(np.linspace(0, pmax, 20), np.linspace(0, pmax, 20), 'k-')
        plt.plot(pdata['lfp_perf'], pdata['spike_perf'], 'ko', alpha=0.7, markersize=10.)
        plt.title(pdata['aprop'])
        pstr = 'R2'
        if pdata['aprop'] == 'category':
            pstr = 'PCC'
        plt.xlabel('LFP %s' % pstr)
        plt.ylabel('Spike %s' % pstr)
        plt.axis('tight')
        plt.xlim(0, pmax)
        plt.ylim(0, pmax)

    multi_plot(perf_list, _plot_scatter, nrows=3, ncols=5, hspace=0.30, wspace=0.30)


def draw_freq_lkrats(agg, df_me):

    # aprops_to_display = ['category', 'maxAmp', 'meanspect', 'stdspect', 'q1', 'q2', 'q3', 'skewspect', 'kurtosisspect',
    #                      'sal', 'entropyspect', 'meantime', 'stdtime', 'entropytime']

    aprops_to_display = ['category', 'maxAmp', 'sal', 'meantime', 'entropytime',
                         'meanspect', 'q1', 'q2', 'q3', 'entropyspect', ]

    assert isinstance(agg, AggregateLFPAndSpikePSDDecoder)
    freqs = agg.freqs
    nbands = len(freqs)

    # compute the significance threshold for each site, use it to normalize the likelihood ratio
    i = agg.df.bird != 'BlaBro09xxF'
    g = agg.df[i].groupby(['bird', 'block', 'segment', 'hemi'])

    num_sites = len(g)

    normed_lkrat_lfp = dict()
    normed_lkrat_spike = dict()
    for aprop in aprops_to_display:
        normed_lkrat_lfp[aprop] = np.zeros([num_sites, nbands])
        normed_lkrat_spike[aprop] = np.zeros([num_sites, nbands])

    for k,((bird,block,segment,hemi),gdf) in enumerate(g):

        i = (gdf.e1 != -1) & (gdf.e1 == gdf.e2) & (gdf.cell_index != -1) & (gdf.decomp == 'spike_psd') & \
            (gdf.exel == False) & (gdf.exfreq == False) & (gdf.aprop == 'q2')
        ncells = i.sum()
        # print '%s,%s,%s,%s # of cells: %d' % (bird, block, segment, hemi, ncells)

        # get the likelihood ratios and normalize them by threshold
        for aprop in aprops_to_display:

            for b in range(1, nbands+1):
                i = (df_me.bird == bird) & (df_me.block == block) & (df_me.segment == segment) & (df_me.hemi == hemi) & \
                    (df_me.band == b)
                if i.sum() != 1:
                    print 'i.sum()=%d, b=%d, (%s,%s,%s,%s)' % (i.sum(), b, bird, block, segment, hemi)
                assert i.sum() == 1

                lkrats_lfp = df_me[i]['lkrat_%s_%s' % (aprop, 'lfp')].values[0]
                lkrats_spike = df_me[i]['lkrat_%s_%s' % (aprop, 'spike')].values[0]

                normed_lkrat_lfp[aprop][k, b-1] = lkrats_lfp
                normed_lkrat_spike[aprop][k, b-1] = lkrats_spike

    # make a list of data for multi plot
    plist = list()
    for aprop in aprops_to_display:
        plist.append({'lfp':normed_lkrat_lfp[aprop], 'spike':normed_lkrat_spike[aprop], 'freqs':freqs, 'aprop':aprop})

    def _plot_freqs(pdata, ax):
        plt.sca(ax)

        lkrat_lfp_mean = pdata['lfp'].mean(axis=0)
        lkrat_spike_mean = pdata['spike'].mean(axis=0)

        plt.axhline(1.0, c='k', linestyle='dashed', alpha=0.7, linewidth=2.0)
        plt.plot(pdata['freqs'], lkrat_lfp_mean, '-', c=COLOR_BLUE_LFP, linewidth=7.0, alpha=0.9)
        plt.plot(pdata['freqs'], lkrat_spike_mean, '-', c=COLOR_YELLOW_SPIKE, linewidth=7.0, alpha=0.9)

        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Normalized Likelihood Ratio')
        leg = custom_legend([COLOR_BLUE_LFP, COLOR_YELLOW_SPIKE], ['LFP', 'Spike'])
        plt.legend(handles=leg, fontsize='x-small')
        plt.title(pdata['aprop'])
        plt.axis('tight')

        if pdata['aprop'] == 'category':
            plt.ylim(0, 16)
        else:
            plt.ylim(0, 7)

    multi_plot(plist, _plot_freqs, nrows=2, ncols=5, hspace=0.30, wspace=0.30, facecolor='w')


def draw_figures(data_dir='/auto/tdrive/mschachter/data'):

    agg_file = os.path.join(data_dir, 'aggregate', 'lfp_and_spike_psd_decoders.h5')
    agg = AggregateLFPAndSpikePSDDecoder.load(agg_file)

    g = agg.df.groupby(['bird', 'block', 'segment', 'hemi'])
    print '# of groups: %d' % len(g)

    df_me,df_se,df_cell = export_dfs(agg)
    # df_me = pd.read_csv(os.path.join(data_dir, 'aggregate', 'multi_electrode_perfs.csv'))
    # df_se = pd.read_csv(os.path.join(data_dir, 'aggregate', 'single_electrode_perfs.csv'))
    # df_cell = pd.read_csv(os.path.join(data_dir, 'aggregate', 'cell_perfs.csv'))

    # draw_perf_hists(agg, df_me)
    # draw_freq_lkrats(agg, df_me)

    # draw_acoustic_perf_boxplots(agg, df_me)
    # draw_category_perf_and_confusion(agg, df_me)

    plt.show()

if __name__ == '__main__':
    set_font()
    draw_figures()

