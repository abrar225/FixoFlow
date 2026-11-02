"""Deterministic score aggregation; not an inference accuracy claim by itself."""
import unicodedata
import re
import random


def words(text):
    text = unicodedata.normalize('NFC', text).casefold()
    return ''.join(' ' if unicodedata.category(c)[0] in 'PS' else c for c in text).split()


def edit_distance(reference, actual):
    previous = list(range(len(actual) + 1))
    for i, token in enumerate(reference, 1):
        row = [i]
        for j, other in enumerate(actual, 1):
            row.append(min(row[-1]+1, previous[j]+1, previous[j-1]+(token != other)))
        previous = row
    return previous[-1]


def percentile(values, quantile):
    """Linear interpolation between ordered observations; seconds in, seconds out."""
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered)-1) * quantile
    low = int(index)
    high = min(low+1, len(ordered)-1)
    return ordered[low] + (ordered[high]-ordered[low])*(index-low)


def summarize(rows):
    # Empty-reference cases have no defined WER. Report their hallucinations
    # separately instead of contaminating the denominator for spoken cases.
    successful = [row for row in rows if row.get('status', 'ok') == 'ok']
    speech = [row for row in successful if row['reference_words'] > 0]
    reference_words = sum(row['reference_words'] for row in speech)
    errors = sum(row['word_errors'] for row in speech)
    characters=sum(row.get('reference_characters',0) for row in successful)
    character_errors=sum(row.get('character_errors',0) for row in successful if row.get('reference_characters',0)>0)
    labels={}
    for row in successful:
        for kind,counts in row.get('exact_labels',{}).items():
            group=labels.setdefault(kind,{'total':0,'retained':0})
            group['total']+=counts['total'];group['retained']+=counts['retained']
    return {
        'cases': len(rows), 'successful_cases':len(successful), 'failed_cases':len(rows)-len(successful),
        'reference_words': reference_words, 'word_errors': errors,
        'normalized_micro_wer': errors/reference_words if reference_words else None,
        'normalized_micro_cer':character_errors/characters if characters else None,
        'exact_labels':labels,
        'empty_reference_cases': len(successful)-len(speech),
        'empty_reference_with_output': sum(bool(row['actual'].strip()) for row in successful if not row['reference_words']),
        'elapsed_seconds_p50': percentile([row['elapsed_seconds'] for row in successful], .5),
        'elapsed_seconds_p95': percentile([row['elapsed_seconds'] for row in successful], .95),
        # Legacy aliases retained for existing callers. The report's explicit
        # measurement scope, not these names, defines whether startup is included.
        'stop_to_text_seconds_p50': percentile([row['elapsed_seconds'] for row in successful], .5),
        'stop_to_text_seconds_p95': percentile([row['elapsed_seconds'] for row in successful], .95),
    }


def score_transcript(reference, actual, labels=None):
    """Raw normalized WER/CER plus exact, case-sensitive labeled substrings.

    Labeled names/numbers/identifiers must be explicit reference terms. Literal
    case and word boundaries are preserved; this does not infer semantics.
    """
    ref_words, actual_words = words(reference), words(actual)
    ref_chars = ''.join(ref_words)
    actual_chars = ''.join(actual_words)
    result = {'reference_words':len(ref_words), 'word_errors':edit_distance(ref_words,actual_words),
              'reference_characters':len(ref_chars), 'character_errors':edit_distance(ref_chars,actual_chars)}
    exact = {}
    for kind, terms in (labels or {}).items():
        if kind not in {'names','numbers','identifiers'}:
            raise ValueError('Unknown exact-match label group: '+kind)
        if not isinstance(terms,list) or any(not isinstance(term,str) or not term or term not in reference for term in terms):
            raise ValueError('Exact-match labels must be nonempty substrings of the reference.')
        retained=0
        for term in terms:
            pattern=(r'(?<!\w)' if term[0].isalnum() or term[0]=='_' else '')+re.escape(term)+(r'(?!\w)' if term[-1].isalnum() or term[-1]=='_' else '')
            expected=len(re.findall(pattern,reference))
            if not expected:raise ValueError('Label is not a complete reference term: '+term)
            retained+=int(len(re.findall(pattern,actual))>=expected)
        exact[kind] = {'total':len(terms), 'retained':retained}
    result['exact_labels'] = exact
    return result


def paired_summary(left, right):
    """Pair by identity/repetition/hash; never silently drop missing/failed cases."""
    def key(row):return row['id'], row.get('repetition',1)
    a, b = {key(row):row for row in left}, {key(row):row for row in right}
    if len(a)!=len(left) or len(b)!=len(right):
        raise ValueError('Duplicate case/repetition in recognizer report.')
    if set(a)!=set(b):
        raise ValueError('Recognizer reports contain different case/repetition sets.')
    pairs=[]
    for ident in sorted(a):
        x,y=a[ident],b[ident]
        if not x.get('audio_sha256') or x['audio_sha256']!=y.get('audio_sha256') or x['reference']!=y['reference']:
            raise ValueError('Audio/reference mismatch for '+str(ident))
        if x.get('language')!=y.get('language') or x.get('timing_phase')!=y.get('timing_phase'):
            raise ValueError('Language/timing phase mismatch for '+str(ident))
        ok=x.get('status','ok')=='ok' and y.get('status','ok')=='ok'
        pairs.append({'id':ident[0], 'repetition':ident[1], 'both_successful':ok,
            'right_minus_left_word_errors':y['word_errors']-x['word_errors'] if ok else None,
            'right_minus_left_seconds':y['elapsed_seconds']-x['elapsed_seconds'] if ok else None})
    return {'pairs':pairs,'paired_cases':len(pairs),'both_successful':sum(p['both_successful'] for p in pairs),
            'left':summarize(left),'right':summarize(right),
            'successful_pairs_only':{
                'left':summarize([a[key] for key in sorted(a) if a[key].get('status','ok')=='ok' and b[key].get('status','ok')=='ok']),
                'right':summarize([b[key] for key in sorted(a) if a[key].get('status','ok')=='ok' and b[key].get('status','ok')=='ok'])},
            'speaker_cluster_bootstrap':paired_bootstrap(a,b),
            'limitations':'Scores exclude failed decodes; failed counts remain visible. Repetitions are not independent speakers. No statistical superiority is inferred.'}


def paired_bootstrap(left,right,draws=1000,seed=0):
    """Descriptive paired WER interval, clustered by declared speaker identity.

    Only matched successful speech cases participate; no speaker labels means no
    interval. Repeated decodes stay inside their speaker cluster.
    """
    groups={}
    for key,x in left.items():
        y=right[key]
        if (x.get('status','ok')!='ok' or y.get('status','ok')!='ok' or
                not x.get('reference_words') or not x.get('speaker_id') or x['speaker_id']!=y.get('speaker_id')):
            continue
        group=groups.setdefault(str(x['speaker_id']),[0,0,0])
        group[0]+=x['reference_words'];group[1]+=x['word_errors'];group[2]+=y['word_errors']
    if len(groups)<2:return {'clusters':len(groups),'interval_95':None,'reason':'At least two declared matched speaker clusters are required.'}
    values=list(groups.values());rng=random.Random(seed);differences=[]
    for _ in range(draws):
        sample=[rng.choice(values) for _ in values]
        differences.append((sum(x[2] for x in sample)-sum(x[1] for x in sample))/sum(x[0] for x in sample))
    return {'clusters':len(groups),'draws':draws,'seed':seed,'quantity':'right-minus-left normalized WER',
            'interval_95':[percentile(differences,.025),percentile(differences,.975)],
            'limitations':'Descriptive interval for sampled speakers/corpus only; excludes failed pairs and does not prove product superiority.'}
