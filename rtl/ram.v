module ram (
    input clk,
    input en,
    input [3:0] we,
    input [13:0] addr,
    input [31:0] wdata,
    output reg [31:0] rdata
);
    reg [31:0] mem [0:16383];

    always @(posedge clk) begin
        if (en) begin
            rdata <= mem[addr];
            if (we[0]) mem[addr][7:0] <= wdata[7:0];
            if (we[1]) mem[addr][15:8] <= wdata[15:8];
            if (we[2]) mem[addr][23:16] <= wdata[23:16];
            if (we[3]) mem[addr][31:24] <= wdata[31:24];
        end
    end
endmodule
