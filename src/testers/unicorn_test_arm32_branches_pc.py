#!/usr/bin/env python2
## -*- coding: utf-8 -*-

from __future__          import print_function
from triton              import *
from unicorn             import *
from unicorn.arm_const   import *
from capstone            import *
from capstone.arm_const  import *

import sys
import pprint
import random

ADDR  = 0x100000
ADDR2 = 0x300000
STACK = 0x500000
HEAP  = 0x600000
SIZE  = 10 * 1024 * 1024

TARGET = 0x200000

CODE2 = [
    (b"\x00\xf0\x20\xe3", "nop"),   # ARM
    # (b"\x00\xbf", "nop"),           # Thumb
]

CODE  = [
    (b"\x01\xf0\x80\x00", "addeq pc, r0, r1"),
    (b"\x01\xf0\x80\x10", "addne pc, r0, r1"),
    (b"\x01\xf0\x80\x20", "addcs pc, r0, r1"),
    (b"\x01\xf0\x80\x30", "addcc pc, r0, r1"),
    (b"\x01\xf0\x80\x40", "addmi pc, r0, r1"),
    (b"\x01\xf0\x80\x50", "addpl pc, r0, r1"),
    (b"\x01\xf0\x80\x60", "addvs pc, r0, r1"),
    (b"\x01\xf0\x80\x70", "addvc pc, r0, r1"),
    (b"\x01\xf0\x80\x80", "addhi pc, r0, r1"),
    (b"\x01\xf0\x80\x90", "addls pc, r0, r1"),
    (b"\x01\xf0\x80\xa0", "addge pc, r0, r1"),
    (b"\x01\xf0\x80\xb0", "addlt pc, r0, r1"),
    (b"\x01\xf0\x80\xc0", "addgt pc, r0, r1"),
    (b"\x01\xf0\x80\xd0", "addle pc, r0, r1"),
    (b"\x01\xf0\x80\xe0", "addal pc, r0, r1"),

    (b"\x01\xf0\xa0\x00", "adceq pc, r0, r1"),
    (b"\x01\xf0\xa0\x10", "adcne pc, r0, r1"),
    (b"\x01\xf0\xa0\x20", "adccs pc, r0, r1"),
    (b"\x01\xf0\xa0\x30", "adccc pc, r0, r1"),
    (b"\x01\xf0\xa0\x40", "adcmi pc, r0, r1"),
    (b"\x01\xf0\xa0\x50", "adcpl pc, r0, r1"),
    (b"\x01\xf0\xa0\x60", "adcvs pc, r0, r1"),
    (b"\x01\xf0\xa0\x70", "adcvc pc, r0, r1"),
    (b"\x01\xf0\xa0\x80", "adchi pc, r0, r1"),
    (b"\x01\xf0\xa0\x90", "adcls pc, r0, r1"),
    (b"\x01\xf0\xa0\xa0", "adcge pc, r0, r1"),
    (b"\x01\xf0\xa0\xb0", "adclt pc, r0, r1"),
    (b"\x01\xf0\xa0\xc0", "adcgt pc, r0, r1"),
    (b"\x01\xf0\xa0\xd0", "adcle pc, r0, r1"),
    (b"\x01\xf0\xa0\xe0", "adcal pc, r0, r1"),
]


def hook_code(mu, address, size, istate):
    print(">>> Tracing instruction at 0x%x, instruction size = 0x%x" %(address, size))

    opcode = mu.mem_read(address, size)
    cpsr = mu.reg_read(ARM_REG_CPSR)
    thumb = (cpsr >> 5) & 0x1

    # print("[UC] CPSR[T]: {:x}".format(thumb))

    # ostate = {
    #     "stack": mu.mem_read(STACK, 0x100),
    #     "heap":  mu.mem_read(HEAP, 0x100),
    #     "r0":    mu.reg_read(UC_ARM_REG_R0),
    #     "r1":    mu.reg_read(UC_ARM_REG_R1),
    #     "r2":    mu.reg_read(UC_ARM_REG_R2),
    #     "r3":    mu.reg_read(UC_ARM_REG_R3),
    #     "r4":    mu.reg_read(UC_ARM_REG_R4),
    #     "r5":    mu.reg_read(UC_ARM_REG_R5),
    #     "r6":    mu.reg_read(UC_ARM_REG_R6),
    #     "r7":    mu.reg_read(UC_ARM_REG_R7),
    #     "r8":    mu.reg_read(UC_ARM_REG_R8),
    #     "r9":    mu.reg_read(UC_ARM_REG_R9),
    #     "r10":   mu.reg_read(UC_ARM_REG_R10),
    #     "r11":   mu.reg_read(UC_ARM_REG_R11),
    #     "r12":   mu.reg_read(UC_ARM_REG_R12),
    #     "sp":    mu.reg_read(UC_ARM_REG_SP),
    #     "r14":   mu.reg_read(UC_ARM_REG_R14),
    #     "pc":    mu.reg_read(UC_ARM_REG_PC),
    #     "n":   ((mu.reg_read(UC_ARM_REG_APSR) >> 31) & 1),
    #     "z":   ((mu.reg_read(UC_ARM_REG_APSR) >> 30) & 1),
    #     "c":   ((mu.reg_read(UC_ARM_REG_APSR) >> 29) & 1),
    #     "v":   ((mu.reg_read(UC_ARM_REG_APSR) >> 28) & 1),
    # }
    # print_state(istate, istate, ostate)

    # if thumb == 1:
    #     print("[EE] Error!")
    #     # sys.exit(-1)

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB if thumb else CS_MODE_ARM)
    md.detail = True
    i = list(md.disasm(opcode, address))[0]
    disasm = "{} {}".format(i.mnemonic, i.op_str)
    opcode_str = " ".join(["%02x" % b for b in opcode])

    print("[UC] Processing: {}\t{:08x}: {}".format(opcode_str, address, disasm))


def emu_with_unicorn(opcode, istate):
    # Initialize emulator in arm32 mode
    mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)

    # map memory for this emulation
    print("[UC] Mapping memory from {:#x} to {:#x}".format(ADDR, ADDR + SIZE));
    mu.mem_map(ADDR, SIZE)

    # write machine code to be emulated to memory
    index = 0
    for op, _ in CODE:
        mu.mem_write(ADDR+index, op)
        index += len(op)

    # Valid memory region to land when testing branches.
    index = 0
    for op, _ in CODE2:
        mu.mem_write(ADDR2+index, op)
        index += len(op)

    apsr = mu.reg_read(UC_ARM_REG_APSR)
    nzcv = istate['n'] << 31 | istate['z'] << 30 | istate['c'] << 29 | istate['v'] << 28

    mu.mem_write(STACK,                bytes(istate['stack']))
    mu.mem_write(HEAP,                 bytes(istate['heap']))
    mu.reg_write(UC_ARM_REG_R0,        istate['r0'])
    mu.reg_write(UC_ARM_REG_R1,        istate['r1'])
    mu.reg_write(UC_ARM_REG_R2,        istate['r2'])
    mu.reg_write(UC_ARM_REG_R3,        istate['r3'])
    mu.reg_write(UC_ARM_REG_R4,        istate['r4'])
    mu.reg_write(UC_ARM_REG_R5,        istate['r5'])
    mu.reg_write(UC_ARM_REG_R6,        istate['r6'])
    mu.reg_write(UC_ARM_REG_R7,        istate['r7'])
    mu.reg_write(UC_ARM_REG_R8,        istate['r8'])
    mu.reg_write(UC_ARM_REG_R9,        istate['r9'])
    mu.reg_write(UC_ARM_REG_R10,       istate['r10'])
    mu.reg_write(UC_ARM_REG_R11,       istate['r11'])
    mu.reg_write(UC_ARM_REG_R12,       istate['r12'])
    mu.reg_write(UC_ARM_REG_SP,        istate['sp'])
    mu.reg_write(UC_ARM_REG_R14,       istate['r14'])
    mu.reg_write(UC_ARM_REG_PC,        istate['pc'])
    mu.reg_write(UC_ARM_REG_APSR,      apsr & 0x0fffffff | nzcv)

    # tracing all instructions with customized callback
    mu.hook_add(UC_HOOK_CODE, hook_code, user_data=istate)

    # emulate code in infinite time & unlimited instructions
    print("[UC] Executing from {:#x} to {:#x}".format(istate['pc'], istate['pc'] + len(opcode)))
    mu.emu_start(istate['pc'], istate['pc'] + len(opcode), count=1)

    ostate = {
        "stack": mu.mem_read(STACK, 0x100),
        "heap":  mu.mem_read(HEAP, 0x100),
        "r0":    mu.reg_read(UC_ARM_REG_R0),
        "r1":    mu.reg_read(UC_ARM_REG_R1),
        "r2":    mu.reg_read(UC_ARM_REG_R2),
        "r3":    mu.reg_read(UC_ARM_REG_R3),
        "r4":    mu.reg_read(UC_ARM_REG_R4),
        "r5":    mu.reg_read(UC_ARM_REG_R5),
        "r6":    mu.reg_read(UC_ARM_REG_R6),
        "r7":    mu.reg_read(UC_ARM_REG_R7),
        "r8":    mu.reg_read(UC_ARM_REG_R8),
        "r9":    mu.reg_read(UC_ARM_REG_R9),
        "r10":   mu.reg_read(UC_ARM_REG_R10),
        "r11":   mu.reg_read(UC_ARM_REG_R11),
        "r12":   mu.reg_read(UC_ARM_REG_R12),
        "sp":    mu.reg_read(UC_ARM_REG_SP),
        "r14":   mu.reg_read(UC_ARM_REG_R14),
        "pc":    mu.reg_read(UC_ARM_REG_PC),
        "n":   ((mu.reg_read(UC_ARM_REG_APSR) >> 31) & 1),
        "z":   ((mu.reg_read(UC_ARM_REG_APSR) >> 30) & 1),
        "c":   ((mu.reg_read(UC_ARM_REG_APSR) >> 29) & 1),
        "v":   ((mu.reg_read(UC_ARM_REG_APSR) >> 28) & 1),
    }
    return ostate

def emu_with_triton(opcode, istate):
    ctx = TritonContext()
    ctx.setArchitecture(ARCH.ARM32)

    inst = Instruction(opcode)
    inst.setAddress(istate['pc'])

    ctx.setConcreteMemoryAreaValue(STACK,           bytes(istate['stack']))
    ctx.setConcreteMemoryAreaValue(HEAP,            bytes(istate['heap']))
    ctx.setConcreteRegisterValue(ctx.registers.r0,  istate['r0'])
    ctx.setConcreteRegisterValue(ctx.registers.r1,  istate['r1'])
    ctx.setConcreteRegisterValue(ctx.registers.r2,  istate['r2'])
    ctx.setConcreteRegisterValue(ctx.registers.r3,  istate['r3'])
    ctx.setConcreteRegisterValue(ctx.registers.r4,  istate['r4'])
    ctx.setConcreteRegisterValue(ctx.registers.r5,  istate['r5'])
    ctx.setConcreteRegisterValue(ctx.registers.r6,  istate['r6'])
    ctx.setConcreteRegisterValue(ctx.registers.r7,  istate['r7'])
    ctx.setConcreteRegisterValue(ctx.registers.r8,  istate['r8'])
    ctx.setConcreteRegisterValue(ctx.registers.r9,  istate['r9'])
    ctx.setConcreteRegisterValue(ctx.registers.r10, istate['r10'])
    ctx.setConcreteRegisterValue(ctx.registers.r11, istate['r11'])
    ctx.setConcreteRegisterValue(ctx.registers.r12, istate['r12'])
    ctx.setConcreteRegisterValue(ctx.registers.sp,  istate['sp'])
    ctx.setConcreteRegisterValue(ctx.registers.r14, istate['r14'])
    ctx.setConcreteRegisterValue(ctx.registers.pc,  istate['pc'])
    ctx.setConcreteRegisterValue(ctx.registers.n,   istate['n'])
    ctx.setConcreteRegisterValue(ctx.registers.z,   istate['z'])
    ctx.setConcreteRegisterValue(ctx.registers.c,   istate['c'])
    ctx.setConcreteRegisterValue(ctx.registers.v,   istate['v'])

    ctx.processing(inst)

    # print()
    # print(inst)
    # for x in inst.getSymbolicExpressions():
    #    print(x)
    # print()

    ostate = {
        "stack": ctx.getConcreteMemoryAreaValue(STACK, 0x100),
        "heap":  ctx.getConcreteMemoryAreaValue(HEAP, 0x100),
        "r0":    ctx.getSymbolicRegisterValue(ctx.registers.r0),
        "r1":    ctx.getSymbolicRegisterValue(ctx.registers.r1),
        "r2":    ctx.getSymbolicRegisterValue(ctx.registers.r2),
        "r3":    ctx.getSymbolicRegisterValue(ctx.registers.r3),
        "r4":    ctx.getSymbolicRegisterValue(ctx.registers.r4),
        "r5":    ctx.getSymbolicRegisterValue(ctx.registers.r5),
        "r6":    ctx.getSymbolicRegisterValue(ctx.registers.r6),
        "r7":    ctx.getSymbolicRegisterValue(ctx.registers.r7),
        "r8":    ctx.getSymbolicRegisterValue(ctx.registers.r8),
        "r9":    ctx.getSymbolicRegisterValue(ctx.registers.r9),
        "r10":   ctx.getSymbolicRegisterValue(ctx.registers.r10),
        "r11":   ctx.getSymbolicRegisterValue(ctx.registers.r11),
        "r12":   ctx.getSymbolicRegisterValue(ctx.registers.r12),
        "sp":    ctx.getSymbolicRegisterValue(ctx.registers.sp),
        "r14":   ctx.getSymbolicRegisterValue(ctx.registers.r14),
        "pc":    ctx.getSymbolicRegisterValue(ctx.registers.pc),
        "n":     ctx.getSymbolicRegisterValue(ctx.registers.n),
        "z":     ctx.getSymbolicRegisterValue(ctx.registers.z),
        "c":     ctx.getSymbolicRegisterValue(ctx.registers.c),
        "v":     ctx.getSymbolicRegisterValue(ctx.registers.v),
    }
    return ostate

def diff_state(state1, state2):
    for k, v in list(state1.items()):
        if (k == 'heap' or k == 'stack') and v != state2[k]:
            print('\t%s: (UC) != (TT)' %(k))
        elif not (k == 'heap' or k == 'stack') and v != state2[k]:
            print('\t%s: %#x (UC) != %#x (TT)' %(k, v, state2[k]))
    return

def print_state(istate, uc_ostate, tt_ostate):
    for k in sorted(istate.keys()):
        if k in ['stack', 'heap']:
            continue

        diff = "!=" if uc_ostate[k] != tt_ostate[k] else "=="

        print("{:>3s}: {:08x} | {:08x} {} {:08x}".format(k, istate[k], uc_ostate[k], diff, tt_ostate[k]))


if __name__ == '__main__':
    # initial state
    state = {
        "stack": b"".join([bytes(255 - i) for i in range(256)]),
        "heap":  b"".join([bytes(i) for i in range(256)]),
        "r0":    0x100000,
        "r1":    0x200000,
        "r2":    random.randint(0x0, 0xffffffff),
        "r3":    random.randint(0x0, 0xffffffff),
        "r4":    random.randint(0x0, 0xffffffff),
        "r5":    random.randint(0x0, 0xffffffff),
        "r6":    random.randint(0x0, 0xffffffff),
        "r7":    random.randint(0x0, 0xffffffff),
        "r8":    random.randint(0x0, 0xffffffff),
        "r9":    random.randint(0x0, 0xffffffff),
        "r10":   random.randint(0x0, 0xffffffff),
        "r11":   random.randint(0x0, 0xffffffff),
        "r12":   random.randint(0x0, 0xffffffff),
        "sp":    STACK,
        "r14":   random.randint(0x0, 0xffffffff),
        "pc":    ADDR,
        "n":     random.randint(0x0, 0x1),
        "z":     random.randint(0x0, 0x1),
        "c":     0, # NOTE: Set on 0 for testing ADC instructions.
        "v":     random.randint(0x0, 0x1),
    }

    # NOTE: Keep track of PC and reset it after testing each instr.
    pc = ADDR
    for opcode, disassembly in CODE:
        print("-" * 80)

        print("[is] pc: {0:x} ({0:d})".format(state['pc']))

        try:
            state['pc'] = pc                                # NOTE: Keep state the same for each execution, just update PC.
            uc_state = emu_with_unicorn(opcode, state)
            tt_state = emu_with_triton(opcode, state)
            pc += len(opcode)
        except Exception as e:
            print('[KO] %s' %(disassembly))
            print('\t%s' %(e))
            sys.exit(-1)

        print("[UC] pc: {0:x} ({0:d})".format(uc_state['pc']))
        print("[TT] pc: {0:x} ({0:d})".format(tt_state['pc']))

        if uc_state != tt_state:
            print('[KO] %s %s' %(" ".join(["%02x" % ord(b) for b in opcode]), disassembly))
            diff_state(uc_state, tt_state)
            print_state(state, uc_state, tt_state)
            sys.exit(-1)

        print('[OK] %s' %(disassembly))

    sys.exit(0)
