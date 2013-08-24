#!/usr/bin/env python

import matplotlib
import pylab as plt
import numpy as np

import re
import os
import sys
import math

def predicate(fn):
    def pred(x):
        if 'persist' not in x[0]:
            return not persist
        return x[0]['persist'] if persist else not x[0]['persist']
    return pred

NEW_ORDER_RGX = re.compile(r'--new-order-remote-item-pct (\d+)')
def extract_pct(x):
  x = x[0]['bench_opts']
  m = NEW_ORDER_RGX.search(x)
  assert m
  p = int(m.group(1))
  assert p >= 0 and p <= 100
  def pn(n, p):
    return 1.0 - (1.0 - p)**n
  def ex(p):
    import math
    return math.fsum([(1.0/11.0)*pn(float(n), p) for n in range(5, 16)])
  return ex(p/100.0) * 100.0

def extract_nthreads(x):
  x = x[0]['threads']
  return x

def deal_with_posK_res(k):
    def fn(x):
        x = x[1]
        if type(x) == list:
            return [e[k] for e in x]
        return x[k]
    return fn

def deal_with_posK_res_percore(k):
    def fn(x):
        nthds = float(extract_nthreads(x))
        x = x[1]
        if type(x) == list:
            return [e[k]/nthds for e in x]
        return x[k]/nthds
    return fn

def longest_line(ls):
    best, bestlen = ls[0], len(ls[0])
    for i in xrange(1, len(ls)):
        if len(ls[i]) > bestlen:
            best, bestline = ls[i], len(ls[i])
    return best

def mean(x):   return sum(x)/len(x)
def median(x): return sorted(x)[len(x)/2]

def mkplot(results, desc, outfilename):
    fig = plt.figure()
    ax = plt.subplot(111)
    lines = []
    for line_desc in desc['lines']:
        predfn = line_desc['extractor']
        line_results = [d for d in results if predfn(d)]
        xpts = map(desc['x-axis'], line_results)
        ypts = map(desc['y-axis'], line_results)
        lines.append({ 'xpts' : xpts, 'ypts' : ypts })
    longest = longest_line([x['xpts'] for x in lines])
    for idx in xrange(len(desc['lines'])):
        line_desc = desc['lines'][idx]
        if 'extend' in line_desc and line_desc['extend']:
            assert len(lines[idx]['xpts']) == 1
            lines[idx]['xpts'] = longest
            lines[idx]['ypts'] = [lines[idx]['ypts'][0] for _ in longest]
    if not desc['show-error-bars']:
        for l in lines:
            ax.plot(l['xpts'], [median(y) for y in l['ypts']])
    else:
        for l in lines:
            ymins = np.array([min(y) for y in l['ypts']])
            ymaxs = np.array([max(y) for y in l['ypts']])
            ymid = np.array([median(y) for y in l['ypts']])
            yerr = np.array([ymid - ymins, ymaxs - ymid])
            ax.errorbar(l['xpts'], ymid, yerr=yerr)

    ax.set_xlabel(desc['x-label'])
    ax.set_ylabel(desc['y-label'])
    ax.set_ylim(ymin = 0)
    ax.legend([l['label'] for l in desc['lines']], loc=desc['legend'])
    if 'y-axis-major-formatter' in desc:
        ax.yaxis.set_major_formatter(desc['y-axis-major-formatter'])
    if 'title' in desc:
        ax.set_title(desc['title'])
    fig.savefig(outfilename, format='pdf')

def mkbar(results, desc, outfilename):
    fig = plt.figure()
    ax = plt.subplot(111)
    bars = []
    for bar_desc in desc['bars']:
        predfn = bar_desc['extractor']
        bar_results = [d for d in results if predfn(d)]
        if len(bar_results) != 1:
            print "bar_results:", bar_results
        assert len(bar_results) == 1, 'bad predicate'
        bars.append({ 'ypts' : desc['y-axis'](bar_results[0]) })
    width = 0.15
    inds = np.arange(len(bars)) * width
    if not desc['show-error-bars']:
        ax.bar(inds, [median(y['ypts']) for y in bars], width)
    else:
        def geterr(ypts):
            ymin = min(ypts)
            ymax = max(ypts)
            ymid = median(ypts)
            yerr = [ymid - ymin, ymax - ymid]
            return yerr
        yerrs = [[geterr(y['ypts'])[0] for y in bars],
                 [geterr(y['ypts'])[1] for y in bars]]
        ax.bar(inds, [median(y['ypts']) for y in bars], width, yerr=yerrs)
    ax.set_xticks(inds + width/2.)
    ax.set_xticklabels( [l['label'] for l in desc['bars']], rotation='vertical' )
    ax.set_ylabel(desc['y-label'])
    ax.set_ylim(ymin = 0)
    if 'y-axis-major-formatter' in desc:
        ax.yaxis.set_major_formatter(desc['y-axis-major-formatter'])
    if 'title' in desc:
        ax.set_title(desc['title'])
    SI = fig.get_size_inches()
    fig.set_size_inches((SI[0]/2., SI[1]))
    fig.savefig(outfilename, format='pdf')

def MFormatter(x, p):
  if x == 0:
    return '0'
  v = float(x)/float(10**6)
  if math.ceil(v) == v:
    return '%dM' % v
  return '%.1fM' % v

def KFormatter(x, p):
  if x == 0:
    return '0'
  v = float(x)/float(10**3)
  if math.ceil(v) == v:
    return '%dK' % v
  return '%.1fK' % v

if __name__ == '__main__':
    matplotlib.rcParams.update({'figure.autolayout' : True})

    #def maflingo_fast_id_gen_extractor(x):
    #    if x[0]['db'] != 'ndb-proto2':
    #        return False
    #    has_sep_tree = x[0]['bench_opts'].find('--enable-separate-tree-per-partition') != -1
    #    has_snapshots = 'disable_snapshots' not in x[0] or not x[0]['disable_snapshots']
    #    has_fast_id_gen = x[0]['bench_opts'].find('--new-order-fast-id-gen') != -1
    #    return not has_sep_tree and has_snapshots and has_fast_id_gen

    def db_extractor(db):
      return lambda x: x[0]['db'] == db

    def name_extractor(name):
      return lambda x: x[0]['name'] == name

    def persist_extractor(mode):
      return lambda x: 'persist' in x[0] and x[0]['persist'] == mode

    def binary_extractor(binary):
      return lambda x: x[0]['binary'] == binary

    def snapshots_extractor(enabled):
      if enabled:
        return lambda x: 'disable_snapshots' not in x[0] or not x[0]['disable_snapshots']
      else:
        return lambda x: 'disable_snapshots' in x[0] and x[0]['disable_snapshots']

    def gc_extractor(enabled):
      if enabled:
        return lambda x: 'disable_gc' not in x[0] or not x[0]['disable_gc']
      else:
        return lambda x: 'disable_gc' in x[0] and x[0]['disable_gc']

    def numa_extractor(enabled):
      if enabled:
        return lambda x: x[0]['numa_memory'] is not None
      else:
        return lambda x: x[0]['numa_memory'] is None

    def sep_trees_extractor(enabled):
      return lambda x: (x[0]['bench_opts'].find('--enable-separate-tree-per-partition') != -1) == enabled

    def workload_mix_extractor(mix):
      mixstr = '--workload-mix %s' % (','.join(map(str, mix)))
      return lambda x: x[0]['bench_opts'].find(mixstr) != -1

    def AND(*extractors):
      def fn(x):
        for ex in extractors:
          if not ex(x):
            return False
        return True
      return fn

    def OR(*extractors):
      def fn(x):
        for ex in extractors:
          if ex(x):
            return True
        return False
      return fn

    #configs = [
    #  {
    #    'file'    : 'istc3-8-16-13_multipart_skew.py',
    #    'outfile' : 'istc3-8-16-13_multipart_skew.pdf',
    #    'x-axis' : extract_nthreads,
    #    'y-axis' : deal_with_posK_res(0),
    #    'lines' : [
    #        {
    #            'label' : 'Partition-Store',
    #            'extractor' : lambda x: x[0]['db'] == 'kvdb-st',
    #            'extend' : True,
    #        },
    #        {
    #            'label' : 'Maflingo',
    #            'extractor' : maflingo_regular_extractor,
    #        },
    #        {
    #            'label' : 'Maflingo+FastIds',
    #            'extractor' : maflingo_fast_id_gen_extractor,
    #        },
    #    ],
    #    'x-label' : 'nthreads',
    #    'y-label' : 'throughput (txns/sec)',
    #    'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(MFormatter),
    #    'x-axis-set-major-locator' : False,
    #    'show-error-bars' : True,
    #    'legend' : 'upper right',
    #  },
    #]

    configs = [
      {
        'file'    : 'istc3-8-21-13_cameraready-1.py',
        'outfile' : 'istc3-8-21-13_cameraready-1-scale_rmw.pdf',
        'x-axis' : extract_nthreads,
        'y-axis' : deal_with_posK_res(0),
        'lines' : [
            {
                'label' : 'Key-Value',
                'extractor' : AND(name_extractor('scale_rmw'), db_extractor('kvdb')),
            },
            {
                'label' : 'Silo',
                'extractor' : AND(name_extractor('scale_rmw'), db_extractor('ndb-proto2')),
            },
            {
                'label' : 'Silo+GlobalTID',
                'extractor' : AND(name_extractor('scale_rmw'), db_extractor('ndb-proto1')),
            },
        ],
        'x-label' : 'nthreads',
        'y-label' : 'throughput (txns/sec)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(MFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
        'legend' : 'upper left',
        'title' : 'YCSB scale',
      },
      {
        'file'    : 'istc3-8-21-13_cameraready-1.py',
        'outfile' : 'istc3-8-21-13_cameraready-1-scale_rmw-percore.pdf',
        'x-axis' : extract_nthreads,
        'y-axis' : deal_with_posK_res_percore(0),
        'lines' : [
            {
                'label' : 'Key-Value',
                'extractor' : AND(name_extractor('scale_rmw'), db_extractor('kvdb')),
            },
            {
                'label' : 'Silo',
                'extractor' : AND(name_extractor('scale_rmw'), db_extractor('ndb-proto2')),
            },
            {
                'label' : 'Silo+GlobalTID',
                'extractor' : AND(name_extractor('scale_rmw'), db_extractor('ndb-proto1')),
            },
        ],
        'x-label' : 'nthreads',
        'y-label' : 'throughput/core (txns/sec/core)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(KFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
        'legend' : 'lower left',
        'title' : 'YCSB scale per-core',
      },
      {
        'file'    : 'istc3-8-22-13_cameraready.py',
        'outfile' : 'istc3-8-22-13_cameraready-scale_tpcc-reg.pdf',
        'x-axis' : extract_nthreads,
        'y-axis' : deal_with_posK_res(0),
        'lines' : [
            {
                'label' : 'Silo',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-none'),
                    workload_mix_extractor([45,43,4,4,4])),
            },
            {
                'label' : 'Silo+PersistTemp',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-temp'),
                    workload_mix_extractor([45,43,4,4,4])),
            },
            {
                'label' : 'Silo+Persist',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-real'),
                    workload_mix_extractor([45,43,4,4,4])),
            },
        ],
        'x-label' : 'nthreads',
        'y-label' : 'throughput (txns/sec)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(KFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
        'legend' : 'upper left',
        'title' : 'TPC-C scale (standard mix)',
      },
      {
        'file'    : 'istc3-8-22-13_cameraready.py',
        'outfile' : 'istc3-8-22-13_cameraready-scale_tpcc-reg-percore.pdf',
        'x-axis' : extract_nthreads,
        'y-axis' : deal_with_posK_res_percore(0),
        'lines' : [
            {
                'label' : 'Silo',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-none'),
                    workload_mix_extractor([45,43,4,4,4])),
            },
            {
                'label' : 'Silo+PersistTemp',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-temp'),
                    workload_mix_extractor([45,43,4,4,4])),
            },
            {
                'label' : 'Silo+Persist',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-real'),
                    workload_mix_extractor([45,43,4,4,4])),
            },
        ],
        'x-label' : 'nthreads',
        'y-label' : 'throughput/core (txns/sec/core)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(KFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
        'legend' : 'lower left',
        'title' : 'TPC-C scale per-core (standard mix)',
      },
      {
        'file'    : 'istc3-8-22-13_cameraready.py',
        'outfile' : 'istc3-8-22-13_cameraready-scale_tpcc-realistic.pdf',
        'x-axis' : extract_nthreads,
        'y-axis' : deal_with_posK_res(0),
        'lines' : [
            {
                'label' : 'Silo',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-none'),
                    workload_mix_extractor([39,37,4,10,10])),
            },
            {
                'label' : 'Silo+PersistTemp',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-temp'),
                    workload_mix_extractor([39,37,4,10,10])),
            },
            {
                'label' : 'Silo+Persist',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-real'),
                    workload_mix_extractor([39,37,4,10,10])),
            },
        ],
        'x-label' : 'nthreads',
        'y-label' : 'throughput (txns/sec)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(KFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
        'legend' : 'upper left',
        'title' : 'TPC-C scale (realistic mix)',
      },
      {
        'file'    : 'istc3-8-22-13_cameraready.py',
        'outfile' : 'istc3-8-22-13_cameraready-scale_tpcc-realistic-percore.pdf',
        'x-axis' : extract_nthreads,
        'y-axis' : deal_with_posK_res_percore(0),
        'lines' : [
            {
                'label' : 'Silo',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-none'),
                    workload_mix_extractor([39,37,4,10,10])),
            },
            {
                'label' : 'Silo+PersistTemp',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-temp'),
                    workload_mix_extractor([39,37,4,10,10])),
            },
            {
                'label' : 'Silo+Persist',
                'extractor' : AND(
                    name_extractor('scale_tpcc'),
                    persist_extractor('persist-real'),
                    workload_mix_extractor([39,37,4,10,10])),
            },
        ],
        'x-label' : 'nthreads',
        'y-label' : 'throughput/core (txns/sec/core)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(KFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
        'legend' : 'lower left',
        'title' : 'TPC-C scale per-core (realistic mix)',
      },
      {
        'file'    : 'istc3-8-22-13_cameraready_2.py',
        'outfile' : 'istc3-8-22-13_cameraready_2-multipart_pct.pdf',
        'x-axis' : extract_pct,
        'y-axis' : deal_with_posK_res(0),
        'lines' : [
            {
                'label' : 'Partition-Store',
                'extractor' : AND(
                    name_extractor('multipart:pct'),
                    db_extractor('kvdb-st')),
            },
            {
                'label' : 'Maflingo',
                'extractor' : AND(
                    name_extractor('multipart:pct'),
                    db_extractor('ndb-proto2'),
                    snapshots_extractor(True)),
            },
            {
                'label' : 'Maflingo+NoSS',
                'extractor' : AND(
                    name_extractor('multipart:pct'),
                    db_extractor('ndb-proto2'),
                    snapshots_extractor(False),
                    sep_trees_extractor(False)),
            },
            {
                'label' : 'Partition-Maflingo+NoSS',
                'extractor' : AND(
                    name_extractor('multipart:pct'),
                    db_extractor('ndb-proto2'),
                    snapshots_extractor(False),
                    sep_trees_extractor(True)),
            },
        ],
        'x-label' : '% cross-partition',
        'y-label' : 'throughput (txns/sec)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(MFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
        'legend' : 'upper right',
      },
      {
        'file'    : 'istc3-8-23-13_cameraready.py',
        'outfile' : 'istc3-8-23-13_cameraready-factor-analysis.pdf',
        'y-axis' : deal_with_posK_res(0),
        'bars' : [
            {
                'label' : 'Baseline',
                'extractor' : AND(
                    name_extractor('factoranalysis'),
                    db_extractor('ndb-proto2'),
                    binary_extractor('../out-factor-gc-nowriteinplace/benchmarks/dbtest'),
                    snapshots_extractor(True),
                    numa_extractor(False)),
            },
            {
                'label' : '+NumaAllocator',
                'extractor' : AND(
                    name_extractor('factoranalysis'),
                    db_extractor('ndb-proto2'),
                    binary_extractor('../out-factor-gc-nowriteinplace/benchmarks/dbtest'),
                    snapshots_extractor(True),
                    numa_extractor(True)),
            },
            {
                'label' : '+Overwrites',
                'extractor' : AND(
                    name_extractor('factoranalysis'),
                    db_extractor('ndb-proto2'),
                    binary_extractor('../out-factor-gc/benchmarks/dbtest'),
                    snapshots_extractor(True),
                    numa_extractor(True)),
            },
            {
                'label' : '-Snapshots',
                'extractor' : AND(
                    name_extractor('factoranalysis'),
                    db_extractor('ndb-proto2'),
                    binary_extractor('../out-factor-gc/benchmarks/dbtest'),
                    snapshots_extractor(False),
                    gc_extractor(True),
                    numa_extractor(True)),
            },
            {
                'label' : '-GC',
                'extractor' : AND(
                    name_extractor('factoranalysis'),
                    db_extractor('ndb-proto2'),
                    binary_extractor('../out-factor-gc/benchmarks/dbtest'),
                    snapshots_extractor(False),
                    gc_extractor(False),
                    numa_extractor(True)),
            },
        ],
        'y-label' : 'throughput (txns/sec)',
        'y-axis-major-formatter' : matplotlib.ticker.FuncFormatter(KFormatter),
        'x-axis-set-major-locator' : False,
        'show-error-bars' : True,
      },
    ]

    FINAL_OUTPUT_FILENAME='istc3-cameraready.pdf'
    from PyPDF2 import PdfFileWriter, PdfFileReader
    output = PdfFileWriter()
    for config in configs:
      g, l = {}, {}
      execfile(config['file'], g, l)
      if 'lines' in config:
        mkplot(l['RESULTS'], config, config['outfile'])
      elif 'bars' in config:
        mkbar(l['RESULTS'], config, config['outfile'])
      else:
        assert False, "bad config"
      inp = PdfFileReader(open(config['outfile'], 'rb'))
      output.addPage(inp.getPage(0))

    output.write(file(FINAL_OUTPUT_FILENAME, 'wb'))
