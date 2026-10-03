#ifndef CUSTOM_OPS_H
#define CUSTOM_OPS_H

#define regnum_zero 0
#define regnum_x1 1
#define regnum_x2 2
#define regnum_a0 10
#define regnum_q0 0
#define regnum_q1 1
#define regnum_q2 2
#define regnum_q3 3

#define r_type_insn(f7, rs2, rs1, f3, rd, opc) \
    .word (((f7) << 25) | ((rs2) << 20) | ((rs1) << 15) | ((f3) << 12) | ((rd) << 7) | (opc))

#define getq_insn(rd, qs) \
    r_type_insn(0b0000000, 0, regnum_ ## qs, 0b100, regnum_ ## rd, 0b0001011)

#define setq_insn(qd, rs) \
    r_type_insn(0b0000001, 0, regnum_ ## rs, 0b010, regnum_ ## qd, 0b0001011)

#define retirq_insn() \
    r_type_insn(0b0000010, 0, 0, 0b000, 0, 0b0001011)

#endif
