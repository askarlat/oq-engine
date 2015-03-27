# Copyright (c) 2010-2015, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with OpenQuake.  If not, see <http://www.gnu.org/licenses/>.

import logging
import operator
import collections
import random
from lxml import etree

from openquake.baselib.general import AccumDict, groupby
from openquake.commonlib.node import read_nodes
from openquake.commonlib import valid, logictree, sourceconverter
from openquake.commonlib.nrml import nodefactory, PARSE_NS_MAP


class DuplicatedID(Exception):
    """Raised when two sources with the same ID are found in a source model"""


class LtRealization(object):
    """
    Composite realization build on top of a source model realization and
    a GSIM realization.
    """
    def __init__(self, ordinal, sm_lt_path, gsim_rlz, weight):
        self.ordinal = ordinal
        self.sm_lt_path = sm_lt_path
        self.gsim_rlz = gsim_rlz
        self.weight = weight

    def __repr__(self):
        if self.col_ids:
            col = ',col=' + ','.join(map(str, sorted(self.col_ids)))
        else:
            col = ''
        return '<%d,%s,w=%s%s>' % (self.ordinal, self.uid, self.weight, col)

    @property
    def gsim_lt_path(self):
        return self.gsim_rlz.lt_path

    @property
    def uid(self):
        """An unique identifier for effective realizations"""
        return '_'.join(self.sm_lt_path) + ',' + self.gsim_rlz.uid


SourceModel = collections.namedtuple(
    'SourceModel', 'name weight path trt_models gsim_lt ordinal samples')


class TrtModel(collections.Sequence):
    """
    A container for the following parameters:

    :param str trt:
        the tectonic region type all the sources belong to
    :param list sources:
        a list of hazardlib source objects
    :param int num_ruptures:
        the total number of ruptures generated by the given sources
    :param min_mag:
        the minimum magnitude among the given sources
    :param max_mag:
        the maximum magnitude among the given sources
    :param gsims:
        the GSIMs associated to tectonic region type
    :param id:
        an optional numeric ID (default None) useful to associate
        the model to a database object
    """
    POINT_SOURCE_WEIGHT = 1 / 40.

    def __init__(self, trt, sources=None, num_ruptures=0,
                 min_mag=None, max_mag=None, gsims=None, id=0):
        self.trt = trt
        self.sources = sources or []
        self.num_ruptures = num_ruptures
        self.min_mag = min_mag
        self.max_mag = max_mag
        self.gsims = gsims or []
        self.id = id
        for src in self.sources:
            self.update(src)

    def update(self, src):
        """
        Update the attributes sources, min_mag, max_mag
        according to the given source.

        :param src:
            an instance of :class:
            `openquake.hazardlib.source.base.BaseSeismicSource`
        """
        assert src.tectonic_region_type == self.trt, (
            src.tectonic_region_type, self.trt)
        self.sources.append(src)
        min_mag, max_mag = src.get_min_max_mag()
        prev_min_mag = self.min_mag
        if prev_min_mag is None or min_mag < prev_min_mag:
            self.min_mag = min_mag
        prev_max_mag = self.max_mag
        if prev_max_mag is None or max_mag > prev_max_mag:
            self.max_mag = max_mag

    def update_num_ruptures(self, src):
        """
        Update the attribute num_ruptures according to the given source.

        :param src:
            an instance of :class:
            `openquake.hazardlib.source.base.BaseSeismicSource`
        :returns:
            the weight of the source, as a function of the number
            of ruptures generated by the source
        """
        num_ruptures = src.count_ruptures()
        self.num_ruptures += num_ruptures
        weight = (num_ruptures * self.POINT_SOURCE_WEIGHT
                  if src.__class__.__name__ == 'PointSource'
                  else num_ruptures)
        return weight

    def split_sources_and_count_ruptures(self, area_source_discretization):
        """
        Split the current .sources and replace them with new ones.
        Also, update the total .num_ruptures and the .weigth of each
        source. Finally, make sure the sources are ordered.

        :param area_source_discretization: parameter from the job.ini
        """
        sources = []
        for src in self:
            for ss in sourceconverter.split_source(
                    src, area_source_discretization):
                ss.weight = self.update_num_ruptures(ss)
                sources.append(ss)
        self.sources = sorted(sources, key=operator.attrgetter('source_id'))

    def __repr__(self):
        return '<%s #%d %s, %d source(s), %d rupture(s)>' % (
            self.__class__.__name__, self.id, self.trt,
            len(self.sources), self.num_ruptures)

    def __lt__(self, other):
        """
        Make sure there is a precise ordering of TrtModel objects.
        Objects with less sources are put first; in case the number
        of sources is the same, use lexicographic ordering on the trts
        """
        num_sources = len(self.sources)
        other_sources = len(other.sources)
        if num_sources == other_sources:
            return self.trt < other.trt
        return num_sources < other_sources

    def __getitem__(self, i):
        return self.sources[i]

    def __iter__(self):
        return iter(self.sources)

    def __len__(self):
        return len(self.sources)


def parse_source_model(fname, converter, apply_uncertainties=lambda src: None):
    """
    Parse a NRML source model and return an ordered list of TrtModel
    instances.

    :param str fname:
        the full pathname of the source model file
    :param converter:
        :class:`openquake.commonlib.source.SourceConverter` instance
    :param apply_uncertainties:
        a function modifying the sources (or do nothing)
    """
    converter.fname = fname
    source_stats_dict = {}
    source_ids = set()
    src_nodes = read_nodes(fname, lambda elem: 'Source' in elem.tag,
                           nodefactory['sourceModel'])
    for no, src_node in enumerate(src_nodes, 1):
        src = converter.convert_node(src_node)
        if src.source_id in source_ids:
            raise DuplicatedID(
                'The source ID %s is duplicated!' % src.source_id)
        apply_uncertainties(src)
        trt = src.tectonic_region_type
        if trt not in source_stats_dict:
            source_stats_dict[trt] = TrtModel(trt)
        source_stats_dict[trt].update(src)
        source_ids.add(src.source_id)
        if no % 10000 == 0:  # log every 10,000 sources parsed
            logging.info('Parsed %d sources from %s', no, fname)

    # return ordered TrtModels
    return sorted(source_stats_dict.itervalues())


def agg_prob(acc, prob):
    """Aggregation function for probabilities"""
    return 1. - (1. - acc) * (1. - prob)


class RlzsAssoc(collections.Mapping):
    """
    Realization association class. It should not be instantiated directly,
    but only via the method :meth:
    `openquake.commonlib.source.CompositeSourceModel.get_rlzs_assoc`.

    :attr realizations: list of LtRealization objects
    :attr gsim_by_trt: list of dictionaries {trt: gsim}
    :attr rlzs_assoc: dictionary {trt_model_id, gsim: rlzs}
    :attr rlzs_by_smodel: dictionary {source_model_ordinal: rlzs}

    For instance, for the non-trivial logic tree in
    :mod:`openquake.qa_tests_data.classical.case_15`, which has 4 tectonic
    region types and 4 + 2 + 2 realizations, there are the following
    associations:

    (0, 'BooreAtkinson2008') ['#0-SM1-BA2008_C2003', '#1-SM1-BA2008_T2002']
    (0, 'CampbellBozorgnia2008') ['#2-SM1-CB2008_C2003', '#3-SM1-CB2008_T2002']
    (1, 'Campbell2003') ['#0-SM1-BA2008_C2003', '#2-SM1-CB2008_C2003']
    (1, 'ToroEtAl2002') ['#1-SM1-BA2008_T2002', '#3-SM1-CB2008_T2002']
    (2, 'BooreAtkinson2008') ['#4-SM2_a3pt2b0pt8-BA2008']
    (2, 'CampbellBozorgnia2008') ['#5-SM2_a3pt2b0pt8-CB2008']
    (3, 'BooreAtkinson2008') ['#6-SM2_a3b1-BA2008']
    (3, 'CampbellBozorgnia2008') ['#7-SM2_a3b1-CB2008']
    """
    def __init__(self, csm_info, rlzs_assoc=None):
        self.csm_info = csm_info
        self.rlzs_assoc = rlzs_assoc or collections.defaultdict(list)
        self.gsim_by_trt = {}  # rlz -> {trt: gsim}
        self.rlzs_by_smodel = collections.OrderedDict()

    @property
    def realizations(self):
        """Flat list with all the realizations"""
        return sum(self.rlzs_by_smodel.itervalues(), [])

    def get_gsims_by_trt_id(self):
        """Returns associations trt_id -> [GSIM instance, ...]"""
        return groupby(
            self.rlzs_assoc, operator.itemgetter(0),
            lambda group: sorted(valid.gsim(gsim)
                                 for trt_id, gsim in group))

    def _add_realizations(self, idx, lt_model, realizations):
        gsims_by_trt = lt_model.gsim_lt.values
        rlzs = []
        for i, gsim_rlz in enumerate(realizations):
            weight = float(lt_model.weight) * float(gsim_rlz.weight)
            rlz = LtRealization(idx, lt_model.path, gsim_rlz, weight)
            rlz.col_ids = set()
            self.gsim_by_trt[rlz] = gsim_rlz.value
            for trt_model in lt_model.trt_models:
                trt = trt_model.trt
                gsim = gsim_rlz.value[trt]
                self.rlzs_assoc[trt_model.id, gsim].append(rlz)
                trt_model.gsims = gsims_by_trt[trt]
                if lt_model.samples > 1:  # oversampling
                    col_idx = self.csm_info.get_col_idx(trt_model.id, i)
                    rlz.col_ids.add(col_idx)
            idx += 1
            rlzs.append(rlz)
        self.rlzs_by_smodel[lt_model.ordinal] = rlzs
        return idx

    def combine(self, results, agg=agg_prob):
        """
        :param results: dictionary (trt_model_id, gsim_name) -> <AccumDict>
        :param agg: aggregation function (default composition of probabilities)
        :returns: a dictionary rlz -> aggregate <AccumDict>

        Example: a case with tectonic region type T1 with GSIMS A, B, C
        and tectonic region type T2 with GSIMS D, E.

        >>> assoc = RlzsAssoc(CompositionInfo([]), {
        ... ('T1', 'A'): ['r0', 'r1'],
        ... ('T1', 'B'): ['r2', 'r3'],
        ... ('T1', 'C'): ['r4', 'r5'],
        ... ('T2', 'D'): ['r0', 'r2', 'r4'],
        ... ('T2', 'E'): ['r1', 'r3', 'r5']})
        ...
        >>> results = {
        ... ('T1', 'A'): 0.01,
        ... ('T1', 'B'): 0.02,
        ... ('T1', 'C'): 0.03,
        ... ('T2', 'D'): 0.04,
        ... ('T2', 'E'): 0.05,}
        ...
        >>> combinations = assoc.combine(results, operator.add)
        >>> for key, value in sorted(combinations.items()): print key, value
        r0 0.05
        r1 0.06
        r2 0.06
        r3 0.07
        r4 0.07
        r5 0.08

        You can check that all the possible sums are performed:

        r0: 0.01 + 0.04 (T1A + T2D)
        r1: 0.01 + 0.05 (T1A + T2E)
        r2: 0.02 + 0.04 (T1B + T2D)
        r3: 0.02 + 0.05 (T1B + T2E)
        r4: 0.03 + 0.04 (T1C + T2D)
        r5: 0.03 + 0.05 (T1C + T2E)

        In reality, the `combine` method is used with dictionaries with the
        hazard curves keyed by intensity measure type and the aggregation
        function is the composition of probability, which however is closer
        to the sum for small probabilities.
        """
        acc = 0
        for key, value in results.iteritems():
            for rlz in self.rlzs_assoc[key]:
                acc = agg(acc, AccumDict({rlz: value}))
        return acc

    def collect_by_rlz(self, dicts):
        """
        :param dicts: a list of dicts with key (trt_model_id, gsim)
        :returns: a dictionary of lists keyed by realization
        """
        by_rlz = AccumDict({rlz: [] for rlz in self.realizations})
        for dic in dicts:
            items = self.combine(dic).iteritems()
            by_rlz += {rlz: [val] for rlz, val in items}
        return by_rlz

    def __iter__(self):
        return self.rlzs_assoc.iterkeys()

    def __getitem__(self, key):
        return self.rlzs_assoc[key]

    def __len__(self):
        return len(self.rlzs_assoc)

    def __str__(self):
        pairs = []
        for key in sorted(self.rlzs_assoc):
            pairs.append(('%s,%s' % key, map(str, self.rlzs_assoc[key])))
        return '{%s}' % '\n'.join('%s: %s' % pair for pair in pairs)


class CompositionInfo(object):
    """
    An object to collect information about the composition of
    a composite source model.
    """
    def __init__(self, source_models):
        self._col_dict = {}  # dictionary trt_id, idx -> col_idx
        self._num_samples = {}  # trt_id -> num_samples
        col_idx = 0
        for sm in source_models:
            for trt_model in sm.trt_models:
                trt_id = trt_model.id
                if sm.samples > 1:
                    self._num_samples[trt_id] = sm.samples
                for idx in range(sm.samples):
                    self._col_dict[trt_id, idx] = col_idx
                    col_idx += 1
                trt_id += 1

    def get_max_samples(self):
        """Return the maximum number of samples of the source model"""
        values = self._num_samples.values()
        if not values:
            return 1
        return max(values)

    def get_num_samples(self, trt_id):
        """
        :param trt_id: tectonic region type object ID
        :returns: how many times the sources of that TRT are to be sampled
        """
        return self._num_samples.get(trt_id, 1)

    def get_col_idx(self, trt_id, idx):
        """
        :param trt_id: tectonic region type object ID
        :param idx: an integer index from 0 to num_samples
        :returns: the SESCollection ordinal
        """
        return self._col_dict[trt_id, idx]

    def get_trt_id(self, col_idx):
        """
        :param col_idx: the ordinal of a SESCollection
        :returns: the ID of the associated TrtModel
        """
        for (trt_id, idx), cid in self._col_dict.iteritems():
            if cid == col_idx:
                return trt_id
        raise KeyError('There is no TrtModel associated to the collection %d!'
                       % col_idx)

    def get_triples(self):
        """
        Yield triples (trt_id, idx, col_idx) in order
        """
        for (trt_id, idx), col_idx in sorted(self._col_dict.iteritems()):
            yield trt_id, idx, col_idx


class CompositeSourceModel(collections.Sequence):
    """
    :param source_model_lt:
        a :class:`openquake.commonlib.logictree.SourceModelLogicTree` instance
    :param source_models:
        a list of :class:`openquake.commonlib.source.SourceModel` tuples
    """
    def __init__(self, source_model_lt, source_models):
        self.source_model_lt = source_model_lt
        self.source_models = list(source_models)
        if len(list(self.sources)) == 0:
            raise RuntimeError('All sources were filtered away')
        self.info = CompositionInfo(source_models)

    @property
    def trt_models(self):
        """
        Yields the TrtModels inside each source model.
        """
        for sm in self.source_models:
            for trt_model in sm.trt_models:
                yield trt_model

    @property
    def sources(self):
        """
        Yield the sources contained in the internal source models.
        """
        for trt_model in self.trt_models:
            for src in trt_model:
                src.trt_model_id = trt_model.id
                yield src

    def get_rlzs_assoc(self, get_weight=lambda tm: tm.num_ruptures):
        """
        Return a RlzsAssoc with fields realizations, gsim_by_trt,
        rlz_idx and trt_gsims.

        :param get_weight: a function trt_model -> positive number
        """
        assoc = RlzsAssoc(self.info)
        random_seed = self.source_model_lt.seed
        num_samples = self.source_model_lt.num_samples
        idx = 0
        for smodel in self.source_models:
            # count the number of ruptures per tectonic region type
            trts = set()
            for trt_model in smodel.trt_models:
                if get_weight(trt_model) > 0:
                    trts.add(trt_model.trt)
            # recompute the GSIM logic tree if needed
            if trts != set(smodel.gsim_lt.tectonic_region_types):
                smodel.gsim_lt.reduce(trts)
            if num_samples:  # sampling
                rnd = random.Random(random_seed + idx)
                rlzs = logictree.sample(smodel.gsim_lt, smodel.samples, rnd)
            else:  # full enumeration
                rlzs = logictree.get_effective_rlzs(smodel.gsim_lt)
            if rlzs:
                idx = assoc._add_realizations(idx, smodel, rlzs)
            else:
                logging.warn('No realizations for %s, %s',
                             '_'.join(smodel.path), smodel.name)
        if assoc.realizations:
            if num_samples:
                assert len(assoc.realizations) == num_samples
                for rlz in assoc.realizations:
                    rlz.weight = 1. / num_samples
            else:
                tot_weight = sum(rlz.weight for rlz in assoc.realizations)
                if tot_weight == 0:
                    raise ValueError('All realizations have zero weight??')
                elif tot_weight < 1:
                    logging.warn('Some source models are not contributing, '
                                 'weights are being rescaled')
                for rlz in assoc.realizations:
                    rlz.weight = rlz.weight / tot_weight
        return assoc

    def __repr__(self):
        """
        Return a string representation of the composite model
        """
        models = ['%d-%s-%s,w=%s [%d trt_model(s)]' % (
            sm.ordinal, sm.name, '_'.join(sm.path), sm.weight,
            len(sm.trt_models)) for sm in self]
        return '<%s\n%s>' % (self.__class__.__name__, '\n'.join(models))

    def __getitem__(self, i):
        """Return the i-th source model"""
        return self.source_models[i]

    def __iter__(self):
        """Return an iterator over the underlying source models"""
        return iter(self.source_models)

    def __len__(self):
        """Return the number of underlying source models"""
        return len(self.source_models)


def _collect_source_model_paths(smlt):
    """
    Given a path to a source model logic tree or a file-like, collect all of
    the soft-linked path names to the source models it contains and return them
    as a uniquified list (no duplicates).
    """
    src_paths = []
    tree = etree.parse(smlt)
    for branch_set in tree.xpath('//nrml:logicTreeBranchSet',
                                 namespaces=PARSE_NS_MAP):

        if branch_set.get('uncertaintyType') == 'sourceModel':
            for branch in branch_set.xpath(
                    './nrml:logicTreeBranch/nrml:uncertaintyModel',
                    namespaces=PARSE_NS_MAP):
                src_paths.append(branch.text)
    return sorted(set(src_paths))
