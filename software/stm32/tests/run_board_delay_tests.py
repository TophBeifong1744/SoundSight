"""Execute the actual board wait function against a phase-controlled TIM2 model.

This verifies software timing arithmetic, not GPIO/pin timing or hardware.
The legacy predicate must fail the same minimum-duration assertion.
"""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from tool_config import gcc_executable

OUT = ROOT / 'software/stm32/build/board-delay'
OUT.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'software/stm32/keil/soundsight_f407/User/soundsight_board.c').read_text()
match = re.search(r'int ss_board_wait_us\(uint32_t us\)\s*\{.*?\n\}', source, re.S)
if not match:
    raise RuntimeError('Cannot find actual wait function')
function = match.group(0)
prefix = r'''
#include <stdint.h>
#include <stdio.h>
#include <inttypes.h>
#define SS_LOOP_LIMIT UINT32_C(2000000)
static struct { int timer_ready; } ss_board_stats;
static uint64_t instant, first_sample, last_sample;
static uint32_t increment, reads;
static uint32_t ss_board_us(void) {
    uint32_t value=(uint32_t)(instant/128U);
    if(reads++==0U) first_sample=instant;
    last_sample=instant;
    instant+=increment;
    return value;
}
static void setup(uint32_t base, unsigned phase, uint32_t step, int ready) {
    instant=(uint64_t)base*128U+phase; reads=0U; increment=step;
    first_sample=last_sample=0U; ss_board_stats.timer_ready=ready;
}
'''
suffix = r'''
static unsigned checks;
#define CHECK(c) do { ++checks; if(!(c)) { \
    printf("FAIL,line=%d,elapsed_128ths=%" PRIu64 "\n",__LINE__,last_sample-first_sample); \
    return 1; } } while(0)
int main(void) {
    const uint32_t durations[]={1U,2U,10U};
    const uint32_t bases[]={100U,UINT32_MAX};
    unsigned b,d,p; uint64_t shortest=UINT64_MAX;
    /* Every CPU-cycle phase in a 1MHz tick at 128MHz, including wrap. */
    for(b=0U;b<2U;++b) for(d=0U;d<3U;++d) for(p=0U;p<128U;++p) {
        setup(bases[b],p,1U,1);
        CHECK(ss_board_wait_us(durations[d])==1);
        CHECK(last_sample-first_sample >= (uint64_t)durations[d]*128U);
        if(d==0U && last_sample-first_sample<shortest) shortest=last_sample-first_sample;
    }
    /* Interrupt-like jumps only extend waiting; uint32 counter wraps. */
    setup(UINT32_MAX,127U,1280U,1);
    CHECK(ss_board_wait_us(1U)==1);
    CHECK(last_sample-first_sample>=128U);
    setup(0U,0U,128U,1);
    CHECK(ss_board_wait_us(100000U)==1);
    CHECK(last_sample-first_sample>=UINT64_C(12800000));
    setup(0U,0U,0U,1);
    CHECK(ss_board_wait_us(1U)==0);
    CHECK(reads<=SS_LOOP_LIMIT+1U);
    setup(0U,0U,0U,1);
    CHECK(ss_board_wait_us(0U)==1);
    CHECK(reads==1U);
    setup(0U,0U,1U,0);
    CHECK(ss_board_wait_us(1U)==0);
    CHECK(reads==1U);
    setup(0U,0U,1U,1);
    CHECK(ss_board_wait_us(100001U)==0);
    CHECK(reads==1U);
    CHECK(ss_board_wait_us(UINT32_MAX)==0);
    printf("BOARD_DELAY_MODEL,PASS,checks=%u,phase_cases=768,min_1us_128ths=%" PRIu64
           ",NOT_PIN_MEASUREMENT\n",checks,shortest);
    return 0;
}
'''

def run(name, command):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True, text=True)
    (OUT / (name + '.log')).write_text(
        'COMMAND: ' + subprocess.list2cmdline([str(x) for x in command]) + '\n' +
        result.stdout + result.stderr + f'\nEXIT_CODE: {result.returncode}\n', encoding='utf-8')
    return result

for name, body in [('fixed', function), ('legacy-mutant', function.replace('<us+1U', '<us'))]:
    if name == 'legacy-mutant' and body == function:
        raise RuntimeError('Legacy mutant was not applied')
    path = OUT / (name + '.c')
    path.write_text(prefix + body + suffix, encoding='utf-8')
    result = run(name + '-compile', [gcc_executable(), '-std=c99', '-O2', '-Wall', '-Wextra',
        '-Wconversion', '-Werror', '-pedantic', '-D__USE_MINGW_ANSI_STDIO=1', path, '-o', OUT / (name + '.exe')])
    if result.returncode:
        raise RuntimeError(result.stderr)
    result = run(name, [OUT / (name + '.exe')])
    if name == 'fixed':
        if result.returncode or 'BOARD_DELAY_MODEL,PASS' not in result.stdout:
            raise RuntimeError(result.stdout + result.stderr)
        print(result.stdout.strip())
    elif result.returncode != 1 or 'FAIL,line=' not in result.stdout:
        raise RuntimeError('Legacy timing defect was not detected')
    else:
        print('LEGACY_MUTANT,REJECTED,minimum_duration_assertion')
