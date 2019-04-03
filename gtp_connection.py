"""
gtp_connection.py
Module for playing games of Go using GoTextProtocol

Parts of this code were originally based on the gtp module 
in the Deep-Go project by Isaac Henrion and Amos Storkey 
at the University of Edinburgh.
"""
import traceback
from sys import stdin, stdout, stderr
from board_util import GoBoardUtil, BLACK, WHITE, EMPTY, BORDER, PASS, \
                       MAXSIZE, coord_to_point
import numpy as np
import re
import time


TIME_LIMIT = 1
stack = list()
debug = list()
INFINITY = 9223372036854775807
NINFINITY = -9223372036854775807

class GtpConnection():

    def __init__(self, go_engine, board, debug_mode = False):
        """
        Manage a GTP connection for a Go-playing engine

        Parameters
        ----------
        go_engine:
            a program that can reply to a set of GTP commandsbelow
        board: 
            Represents the current board state.
        """
        self._debug_mode = debug_mode
        self.go_engine = go_engine
        self.board = board
        self.commands = {
            "protocol_version": self.protocol_version_cmd,
            "quit": self.quit_cmd,
            "name": self.name_cmd,
            "boardsize": self.boardsize_cmd,
            "showboard": self.showboard_cmd,
            "clear_board": self.clear_board_cmd,
            "komi": self.komi_cmd,
            "version": self.version_cmd,
            "known_command": self.known_command_cmd,
            "genmove": self.genmove_cmd,
            "list_commands": self.list_commands_cmd,
            "play": self.play_cmd,
            "legal_moves": self.legal_moves_cmd,
            "heuristic": self.heuristic_cmd,
            "gogui-rules_game_id": self.gogui_rules_game_id_cmd,
            "gogui-rules_board_size": self.gogui_rules_board_size_cmd,
            "gogui-rules_legal_moves": self.gogui_rules_legal_moves_cmd,
            "gogui-rules_side_to_move": self.gogui_rules_side_to_move_cmd,
            "gogui-rules_board": self.gogui_rules_board_cmd,
            "gogui-rules_final_result": self.gogui_rules_final_result_cmd,
            "gogui-analyze_commands": self.gogui_analyze_cmd,

            "timelimit": self.timelimit_cmd,
            "printtime": self.printtime_cmd,
            "push": self.save_board_state,
            "undo": self.undo_board,
            "solve": self.minimax_solve,
            "test": self.test
          
        }

        # used for argument checking
        # values: (required number of arguments, 
        #          error message on argnum failure)
        self.argmap = {
            "boardsize": (1, 'Usage: boardsize INT'),
            "komi": (1, 'Usage: komi FLOAT'),
            "known_command": (1, 'Usage: known_command CMD_NAME'),
            "genmove": (1, 'Usage: genmove {w,b}'),
            "play": (2, 'Usage: play {b,w} MOVE'),
            "legal_moves": (1, 'Usage: legal_moves {w,b}')
        }

    def test(self, args):
        print('\033[91m')
        print("In red")
        print('\033[0m')
    
    def write(self, data):
        stdout.write(data) 

    def flush(self):
        stdout.flush()

    def start_connection(self):
        """
        Start a GTP connection. 
        This function continuously monitors standard input for commands.
        """
        line = stdin.readline()
        while line:
            self.get_cmd(line)
            line = stdin.readline()

    def get_cmd(self, command):
        """
        Parse command string and execute it
        """
        if len(command.strip(' \r\t')) == 0:
            return
        if command[0] == '#':
            return
        # Strip leading numbers from regression tests
        if command[0].isdigit():
            command = re.sub("^\d+", "", command).lstrip()

        elements = command.split()
        if not elements:
            return
        command_name = elements[0]; args = elements[1:]
        if self.has_arg_error(command_name, len(args)):
            return
        if command_name in self.commands:
            try:
                self.commands[command_name](args)
            except Exception as e:
                self.debug_msg("Error executing command {}\n".format(str(e)))
                self.debug_msg("Stack Trace:\n{}\n".
                               format(traceback.format_exc()))
                raise e
        else:
            self.debug_msg("Unknown command: {}\n".format(command_name))
            self.error('Unknown command')
            stdout.flush()

    def has_arg_error(self, cmd, argnum):
        """
        Verify the number of arguments of cmd.
        argnum is the number of parsed arguments
        """
        if cmd in self.argmap and self.argmap[cmd][0] != argnum:
            self.error(self.argmap[cmd][1])
            return True
        return False

    def debug_msg(self, msg):
        """ Write msg to the debug stream """
        if self._debug_mode:
            stderr.write(msg)
            stderr.flush()

    def error(self, error_msg):
        """ Send error msg to stdout """
        stdout.write('? {}\n\n'.format(error_msg))
        stdout.flush()

    def respond(self, response=''):
        """ Send response to stdout """
        stdout.write('= {}\n\n'.format(response))
        stdout.flush()

    def reset(self, size):
        """
        Reset the board to empty board of given size
        """
        self.board.reset(size)

    def board2d(self):
        return str(GoBoardUtil.get_twoD_board(self.board))
        
    def protocol_version_cmd(self, args):
        """ Return the GTP protocol version being used (always 2) """
        self.respond('2')

    def quit_cmd(self, args):
        """ Quit game and exit the GTP interface """
        self.respond()
        exit()

    def name_cmd(self, args):
        """ Return the name of the Go engine """
        self.respond(self.go_engine.name)

    def version_cmd(self, args):
        """ Return the version of the  Go engine """
        self.respond(self.go_engine.version)

    def clear_board_cmd(self, args):
        """ clear the board """
        self.reset(self.board.size)
        self.respond()

    def boardsize_cmd(self, args):
        """
        Reset the game with new boardsize args[0]
        """
        self.reset(int(args[0]))
        self.respond()

    def showboard_cmd(self, args):
        self.respond('\n' + self.board2d())

    def komi_cmd(self, args):
        """
        Set the engine's komi to args[0]
        """
        self.go_engine.komi = float(args[0])
        self.respond()

    def known_command_cmd(self, args):
        """
        Check if command args[0] is known to the GTP interface
        """
        if args[0] in self.commands:
            self.respond("true")
        else:
            self.respond("false")

    def list_commands_cmd(self, args):
        """ list all supported GTP commands """
        self.respond(' '.join(list(self.commands.keys())))

    def legal_moves_cmd(self, args):
        """
        List legal moves for color args[0] in {'b','w'}
        """
        board_color = args[0].lower()
        color = color_to_int(board_color)
        moves = GoBoardUtil.generate_legal_moves(self.board, color)
        gtp_moves = []
        for move in moves:
            coords = point_to_coord(move, self.board.size)
            gtp_moves.append(format_point(coords))
        sorted_moves = ' '.join(sorted(gtp_moves))
        self.respond(sorted_moves)

    #Heuristic Function Command for testing
    def heuristic_cmd(self, args):
        self.respond(self.board.StatisticallyEvaluate())

    def play_cmd(self, args):
        """
        play a move args[1] for given color args[0] in {'b','w'}
        """
        try:
            board_color = args[0].lower()
            board_move = args[1]
            if board_color != "b" and board_color !="w":
                self.respond("illegal move: \"{}\" wrong color".format(board_color))
                return
            color = color_to_int(board_color)
            if args[1].lower() == 'pass':
                self.board.play_move(PASS, color)
                self.board.current_player = GoBoardUtil.opponent(color)
                self.respond()
                return
            coord = move_to_coord(args[1], self.board.size)
            if coord:
                move = coord_to_point(coord[0],coord[1], self.board.size)
            else:
                self.error("Error executing move {} converted from {}"
                           .format(move, args[1]))
                return
            if not self.board.play_move_gomoku(move, color):
                self.respond("illegal move: \"{}\" occupied".format(board_move))
                return
            else:
                self.debug_msg("Move: {}\nBoard:\n{}\n".
                                format(board_move, self.board2d()))
            self.respond()
        except Exception as e:
            self.respond('{}'.format(str(e)))

    def genmove_cmd(self, args):
        """
        Generate a move for the color args[0] in {'b', 'w'}, for the game of gomoku.
        """
        board_color = args[0].lower()
        color = color_to_int(board_color)
        game_end, winner = self.board.check_game_end_gomoku()
        if game_end:
            if winner == color:
                self.respond("pass")
            else:
                self.respond("resign")
            return
        board_copy = self.board.copy()
        is_win, move = Minimax(board_copy, 2, color)
        if not is_win:
            move = self.go_engine.get_move(self.board, color)
        if move == PASS:
            self.respond("pass")
            return
        move_coord = point_to_coord(move, self.board.size)
        move_as_string = format_point(move_coord)
        if self.board.is_legal_gomoku(move, color):
            self.board.play_move_gomoku(move, color)
            self.respond(move_as_string)
        else:
            self.respond("illegal move: {}".format(move_as_string))

    def gogui_rules_game_id_cmd(self, args):
        self.respond("Gomoku")
    
    def gogui_rules_board_size_cmd(self, args):
        self.respond(str(self.board.size))
    
    def legal_moves_cmd(self, args):
        """
            List legal moves for color args[0] in {'b','w'}
            """
        board_color = args[0].lower()
        color = color_to_int(board_color)
        moves = GoBoardUtil.generate_legal_moves(self.board, color)
        gtp_moves = []
        for move in moves:
            coords = point_to_coord(move, self.board.size)
            gtp_moves.append(format_point(coords))
        sorted_moves = ' '.join(sorted(gtp_moves))
        self.respond(sorted_moves)

    def gogui_rules_legal_moves_cmd(self, args):
        game_end,_ = self.board.check_game_end_gomoku()
        if game_end:
            self.respond()
            return
        moves = GoBoardUtil.generate_legal_moves_gomoku(self.board)
        gtp_moves = []
        for move in moves:
            coords = point_to_coord(move, self.board.size)
            gtp_moves.append(format_point(coords))
        sorted_moves = ' '.join(sorted(gtp_moves))
        self.respond(sorted_moves)
    
    def gogui_rules_side_to_move_cmd(self, args):
        color = "black" if self.board.current_player == BLACK else "white"
        self.respond(color)
    
    def gogui_rules_board_cmd(self, args):
        size = self.board.size
        str = ''
        for row in range(size-1, -1, -1):
            start = self.board.row_start(row + 1)
            for i in range(size):
                point = self.board.board[start + i]
                if point == BLACK:
                    str += 'X'
                elif point == WHITE:
                    str += 'O'
                elif point == EMPTY:
                    str += '.'
                else:
                    assert False
            str += '\n'
        self.respond(str)
    
    def gogui_rules_final_result_cmd(self, args):
        game_end, winner = self.board.check_game_end_gomoku()
        moves = self.board.get_empty_points()
        board_full = (len(moves) == 0)
        if board_full and not game_end:
            self.respond("draw")
            return
        if game_end:
            color = "black" if winner == BLACK else "white"
            self.respond(color)
        else:
            self.respond("unknown")

    def gogui_analyze_cmd(self, args):
        self.respond("pstring/Legal Moves For ToPlay/gogui-rules_legal_moves\n"
                     "pstring/Side to Play/gogui-rules_side_to_move\n"
                     "pstring/Final Result/gogui-rules_final_result\n"
                     "pstring/Board Size/gogui-rules_board_size\n"
                     "pstring/Rules GameID/gogui-rules_game_id\n"
                     "pstring/Show Board/gogui-rules_board\n"
                     )
    def timelimit_cmd(self, args):
        """
        Sets the maximum time to use for all following genmove or solve commands, 
        until it is changed by another timelimit command.
        """
        global TIME_LIMIT
        setGlobalTime(int(args[0]))
        self.respond('')

    def printtime_cmd(self, args):
        print(TIME_LIMIT)

    def save_board_state(self, args):
        save_board(self.board)
        
    def undo_board(self, args):
        self.board = undo();

    def minimax_solve(self, args):
        depth = 2
        win, move = Minimax(self.board.copy(), depth, self.board.current_player)
        #DEBUG
        #print("minimax_solve: ")
        #print(str(GoBoardUtil.get_twoD_board(self.board)))
        #DEBUG
        #print(debug)
        #print(stack)

        #if win is 4, then solver ran out of time
        if win == 4:
            self.respond("unknown")
        
        elif win == 2:
            if move == None:
                self.respond(int_to_color(seslf.board.current_player))
            else:
                move_coord = point_to_coord(move, self.board.size)
                move_as_string = format_point(move_coord)
                string = int_to_color(self.board.current_player) + " " + move_as_string
                self.respond(string)
        elif win == 1:
            move_coord = point_to_coord(move, self.board.size)
            move_as_string = format_point(move_coord)
            string = "draw " + move_as_string
            self.respond(string)
        else:
            self.respond(int_to_color(opposite_color(self.board.current_player)))
        
        

def point_to_coord(point, boardsize):
    """
    Transform point given as board array index 
    to (row, col) coordinate representation.
    Special case: PASS is not transformed
    """
    if point == PASS:
        return PASS
    else:
        NS = boardsize + 1
        return divmod(point, NS)

def format_point(move):
    """
    Return move coordinates as a string such as 'a1', or 'pass'.
    """
    column_letters = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
    #column_letters = "abcdefghjklmnopqrstuvwxyz"
    if move == PASS:
        return "pass"
    row, col = move
    if not 0 <= row < MAXSIZE or not 0 <= col < MAXSIZE:
        raise ValueError
    return column_letters[col - 1]+ str(row) 
    
def move_to_coord(point_str, board_size):
    """
    Convert a string point_str representing a point, as specified by GTP,
    to a pair of coordinates (row, col) in range 1 .. board_size.
    Raises ValueError if point_str is invalid
    """
    if not 2 <= board_size <= MAXSIZE:
        raise ValueError("board_size out of range")
    s = point_str.lower()
    if s == "pass":
        return PASS
    try:
        col_c = s[0]
        if (not "a" <= col_c <= "z") or col_c == "i":
            raise ValueError
        col = ord(col_c) - ord("a")
        if col_c < "i":
            col += 1
        row = int(s[1:])
        if row < 1:
            raise ValueError
    except (IndexError, ValueError):
        raise ValueError("illegal move: \"{}\" wrong coordinate".format(s))
    if not (col <= board_size and row <= board_size):
        raise ValueError("illegal move: \"{}\" wrong coordinate".format(s))
    return row, col

def color_to_int(c):
    """convert character to the appropriate integer code"""
    color_to_int = {"b": BLACK , "w": WHITE, "e": EMPTY, 
                    "BORDER": BORDER}
    return color_to_int[c]

def int_to_color(n):
    """convert integer to the appropriate character code"""
    int_to_color = {BLACK: "b" , WHITE: "w", EMPTY: "e",
                    BORDER: "BORDER"}
    return int_to_color[n]

def opposite_color(color):
    if color == BLACK:
        return WHITE
    elif color == WHITE:
        return BLACK

def save_board(board):
    b = board.copy()
    stack.append(b)
    debug.append("Stored board")

def undo():
    debug.append("Undid board")
    if len(stack) == 0:
        print("Stack is empty!")
    return stack.pop()

def setGlobalTime(time):
    global TIME_LIMIT
    TIME_LIMIT = time

#simply returns the right move, if any
def Minimax(board, depth, color):
    start_time = time.time()
    moves = GoBoardUtil.generate_legal_moves_gomoku(board)
    best_points = 0
    best_move = None
    is_win = 0
    alpha = NINFINITY
    beta = INFINITY

    #special case: check to see if current board already has a winner
    win, col = board.check_game_end_gomoku()
    if win == True:
        #if the opposite color already won, then return win=0
        if col == opposite_color(color):
            return 0, None;
        #if our current winner already won, return
    
    for move in moves:
        time_elapsed = time.time() - start_time
        if time_elapsed >= TIME_LIMIT:
            return 4, None
        #DEBUG - remove later
        print(time_elapsed)
        save_board(board)
        board.play_move_gomoku(move, color)
        win, col, points = MinimaxBooleanAND(board, depth-1, opposite_color(color), alpha, beta)

        #DEBUG
        #move_coord = point_to_coord(move, board.size)
        #move_as_string = format_point(move_coord)
        #print("move: " + move_as_string + ", points: " + str(points))

        
        if win and points > best_points:
            is_win = 2
            best_move = move
            best_points = points
            alpha = best_points

        #process a draw, best condition if win not an option
        if (is_win != 2 and points == 0):
            is_win = 1
            best_move = move
            
        board = undo()

    return is_win, best_move


#minimax solver implementation ahead
def MinimaxBooleanOR(board, depth, color, alpha, beta):
    moves = GoBoardUtil.generate_legal_moves_gomoku(board)
    best_points = 0
    is_win = False

    #DEBUG - remove later
    global TIME_LIMIT
    print(TIME_LIMIT)
    
    #base case
    if (depth == 0 or len(moves) == 0):
        if len(moves)==0:
            return board.StatisticallyEvaluate(False)
        return board.StatisticallyEvaluate()
        

    for move in moves:        
        
        save_board(board)
        board.play_move_gomoku(move, color)
        win, col, points = MinimaxBooleanAND(board, depth-1, opposite_color(color), alpha, beta)
        
        if col != color:
            win = False
            points = -points
        if win:
            is_win = True
        if points > best_points:
            best_points = points
        board = undo()
        
        # deal with alpha-beta
        #if best_points >= beta:
            #alert("beta cutoff: " + str(beta))
            #return is_win, color, best_points
        if best_points >= alpha:
            alpha = best_points
        
    #DEBUG
    #print("MinimaxOR: ")
    #print(str(GoBoardUtil.get_twoD_board(board)))
    return is_win, color, best_points

def MinimaxBooleanAND(board, depth, color, alpha, beta):
    moves = GoBoardUtil.generate_legal_moves_gomoku(board)
    worst_points = 10000
    
    #base case
    if (depth == 0 or len(moves) == 0):
        if len(moves)==0:
            return board.StatisticallyEvaluate(False)
        return board.StatisticallyEvaluate()

    for move in moves:
        
        save_board(board)
        board.play_move_gomoku(move, color)
        win, col, points = MinimaxBooleanOR(board, depth-1, opposite_color(color), alpha, beta)
        
        if col != opposite_color(color):
            win = False
            points = -points
        if not win:
            board = undo()
            return False, opposite_color(color), points
        if points < worst_points:
            worst_points = points

        board = undo()

        # deal with alpha-beta values
        #if worst_points <= alpha:
            #alert("alpha cutoff: " + str(alpha))
            #return False, opposite_color(color), worst_points
        if worst_points <= beta:
            beta = points

    #DEBUG
    #print("Worst points: " + str(worst_points))
    #print("MinimaxAND: ")
    #print(str(GoBoardUtil.get_twoD_board(board)))
    return True, opposite_color(color), worst_points

def alert(message):
        print('\033[91m')
        print(message)
        print('\033[0m')    

