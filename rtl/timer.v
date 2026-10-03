module timer (
    input clk,
    input resetn,
    input en,
    input [3:0] wstrb,
    input [3:0] addr,
    input [31:0] wdata,
    output reg [31:0] rdata,
    output irq
);
    localparam REG_COUNT = 2'd0;
    localparam REG_COMPARE = 2'd1;
    localparam REG_CTRL = 2'd2;
    localparam REG_STATUS = 2'd3;

    wire wr = en && |wstrb;
    wire [1:0] reg_sel = addr[3:2];

    reg [31:0] count;
    reg [31:0] compare;
    reg enable;
    reg irq_en;
    reg reload;
    reg match;

    assign irq = match && irq_en;

    always @* begin
        case (reg_sel)
            REG_COUNT: rdata = count;
            REG_COMPARE: rdata = compare;
            REG_CTRL: rdata = {29'd0, reload, irq_en, enable};
            REG_STATUS: rdata = {31'd0, match};
            default: rdata = 32'd0;
        endcase
    end

    always @(posedge clk) begin
        if (!resetn) begin
            count <= 0;
            compare <= 32'hffffffff;
            enable <= 0;
            irq_en <= 0;
            reload <= 0;
            match <= 0;
        end else begin
`ifndef INJECT_TIMER_W1C_IGNORED
            if (wr && reg_sel == REG_STATUS && wdata[0]) match <= 0;
`endif

            if (enable) begin
                if (count == compare) begin
                    match <= 1;
                    count <= reload ? 32'd0 : count + 1;
                end else begin
                    count <= count + 1;
                end
            end

            if (wr) begin
                case (reg_sel)
                    REG_COUNT: count <= wdata;
                    REG_COMPARE: compare <= wdata;
                    REG_CTRL: {reload, irq_en, enable} <= wdata[2:0];
                    default: ;
                endcase
            end
        end
    end
endmodule
