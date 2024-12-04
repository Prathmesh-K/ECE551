package tb_tasks;

  localparam CAL_GYRO = 16'h2000;

  localparam POS_ACK = 8'hA5;
  localparam ACK = 8'h5A;
  
  // Task to initialize all input signals to default values.
  task automatic Initialize(ref clk, ref RST_n, ref send_cmd, ref [15:0] cmd);
    begin
        // Initialize all signals to the default values.
        clk = 1'b0;
        RST_n = 1'b0;
        send_cmd = 1'b0;
        cmd = 16'h0000;
        repeat (2) @(posedge clk); // Wait for a full clock cycle for system to reset.
        @(negedge clk); 
        RST_n = 1'b1; // Deassert RST_n on negative edge of clock.
        repeat (500) @(negedge clk); // Wait for a while.
    end
  endtask

  // Task to wait for a signal to be asserted, otherwise times out.
  task automatic TimeoutTask(ref sig, ref clk, input int clks2wait, input string signal);
    fork
      begin : timeout
        repeat(clks2wait) @(posedge clk);
        $display("ERROR: %s not getting asserted and/or held at its value.", signal);
        $stop(); // Stop simulation on error.
      end : timeout
      begin
        @(posedge sig) disable timeout; // Disable timeout if sig is asserted.
      end
    join
  endtask
  
  // Task to send a command to the DUT and verify that the command is sent.
  task automatic SendCmd(input [15:0] cmd_to_send, ref [15:0] cmd, ref clk, ref send_cmd, ref cmd_sent);
    begin
        // cmd is the command to send.
        cmd = cmd_to_send;

        @(negedge clk) send_cmd = 1'b1; // Assert snd_cmd and begin transmission.
        @(negedge clk) send_cmd = 1'b0; // Deassert snd_cmd after one clock cycle.

        // Wait for 60000 clocks for cmd_sent to be asserted, else timeout.
        TimeoutTask(.sig(cmd_sent), .clk(clk) .clks2wait(60000), .signal("cmd_sent"));
    end
  endtask

  // Task to check if a positive acknowledge is received from the DUT.
  task automatic ChkPosAck(ref resp_rdy, ref clk, ref resp);
    // Wait 60000 clock cycles, and ensure that a response is received.
    TimeoutTask(.sig(resp_rdy), .clk(clk) .clks2wait(60000), .signal("resp_rdy"));

    // Check that a positive acknowledge of 0xA5 is received.
    @(negedge clk) begin
      if (resp !== POS_ACK) begin
        $display("ERROR: resp should have been 8'hA5 but was 0x%h", resp);
        $stop(); 
      end
    end
  endtask

  // Task to check if an acknowledge is received from the DUT.
  task automatic ChkAck(ref resp_rdy, ref clk, ref resp);
    // Wait 60000 clock cycles, and ensure that a response is received.
    TimeoutTask(.sig(resp_rdy), .clk(clk) .clks2wait(60000), .signal("resp_rdy"));

    // Check that an acknowledge of 0x5A is received.
    @(negedge clk) begin
      if (resp !== ACK) begin
        $display("ERROR: resp should have been 8'h5A but was 0x%h", resp);
        $stop(); 
      end
    end
  endtask

  // Task to check if the Knight moved to the correct position within a range.
  task automatic ChkPos(input [2:0] target_xx, input [2:0] target_yy, ref [14:0] actual_xx, ref [14:0] actual_yy);
    @(negedge clk) begin
      // Check xx within KnightPhysics +/- 0x200.
      if ((actual_xx < {target_xx, 12'h600}) || (actual_xx > {target_xx, 12'hA00}) ) begin
        $display("ERROR: xx position is more than 0x200 outside of target position\ntarget: 0x%h\nactual: 0x%h", {target_xx, 12'h800}, actual_xx);
        $stop();
      end

      // Check yy within KnightPhysics +/- 0x200.
      if ((actual_yy < {target_yy, 12'h600}) || (actual_yy > {target_yy, 12'hA00}) ) begin
        $display("ERROR: yy position is more than 0x200 outside of target position\ntarget: 0x%h\nactual: 0x%h", {target_yy, 12'h800}, actual_yy);
        $stop();
      end
    end
  endtask

  // Task to check if the Knight heading is pointed in the correct direction.
  task automatic ChkHeading(input signed [15:0] target_heading, ref signed [15:0] actual_heading);
    @(negedge clk) begin
      // Check heading within KnightPhysics +/- 0x2C.
      if ((actual_xx < (target_heading - $signed(8'h2C))) || (actual_xx > (target_heading + $signed(8'h2C))) ) begin
        $display("ERROR: heading is more than 0x2C outside of target heading\ntarget: 0x%h\nactual: 0x%h", target_heading, actual_heading);
        $stop();
      end
    end
  endtask

  // Task to check if the Knight is actively moving forward.
  task automatic WaitMoving(ref signed [16:0] velocity_sum);
    repeat(3000000) @(posedge clk) begin
      if (velocity_sum < $signed(17'h00200)) begin
        $display("ERROR: velocity sum is not crossing 0x200 threshold\nvelocity sum: 0x%h", velocity_sum);
        $stop();
      end
    end
  endtask
endpackage
